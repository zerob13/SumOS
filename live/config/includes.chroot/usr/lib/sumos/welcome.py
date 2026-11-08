#!/usr/bin/python3
"""A small native first-session UI; no browser or HTTP listener is needed."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import queue
import subprocess
import tkinter as tk
from tkinter import messagebox
from urllib.parse import urlsplit
import qrcode
from PIL import Image, ImageTk
from rpc import Client, PROVIDER


class Welcome:
    def __init__(self, root):
        self.root = root
        self.attempt = None
        self.remote_attempt = None
        self.timers = set()
        self.generation = 0
        self.closed = False
        self.busy = False
        self.events = queue.Queue()
        self.worker = ThreadPoolExecutor(max_workers=1)
        root.title('SumOS · Dim')
        root.geometry('650x700')
        root.configure(bg='#101816')
        root.protocol('WM_DELETE_WINDOW', self.close)
        try:
            banner = Image.open('/usr/share/backgrounds/sumos/dim-banner.png')
            banner.thumbnail((600, 60))
            self.banner = ImageTk.PhotoImage(banner)
            tk.Label(root, image=self.banner, bg='#101816').pack(pady=8)
        except FileNotFoundError:
            pass
        self.label('SumOS', 26).pack()
        self.label('A small Linux. A capable agent.', 13).pack(pady=5)
        self.status = self.label('Starting Dim…', 12)
        self.status.pack(pady=8)
        self.qr = tk.Label(root, bg='#101816')
        self.qr.pack()
        self.code = self.label('', 22)
        self.code.pack(pady=5)
        self.url = self.label('', 10)
        self.url.configure(wraplength=600)
        self.url.pack()
        region = tk.Frame(root, bg='#101816')
        region.pack(pady=8)
        self.directory = tk.StringVar(value='https://dimagent.cn')
        for name, url in [('China', 'https://dimagent.cn'), ('Global', 'https://dimagent.com')]:
            tk.Radiobutton(region, text=name, variable=self.directory, value=url,
                           bg='#101816', fg='#b9f4d4', selectcolor='#20372c',
                           command=self.begin).pack(side='left')
        actions = tk.Frame(root, bg='#101816')
        actions.pack(pady=6)
        for text, action in [('Retry sign-in', self.begin), ('Open agent', self.open_agent),
                             ('Pause agent', self.pause), ('Network', self.network)]:
            tk.Button(actions, text=text, command=action).pack(side='left', padx=4)
        if Path('/run/live/medium').exists():
            tk.Button(actions, text='Install OS', command=lambda: subprocess.Popen(['debian-installer-launcher'])).pack(side='left', padx=4)
        tk.Button(root, text='Install Google Chrome…', command=self.install_chrome).pack(pady=8)
        self.label('Chrome is downloaded from Google after you accept its terms.', 10).pack()
        if Path('/run/live/medium').exists():
            self.label('Install to disk before signing in to keep your account and files.', 10).pack(pady=6)
        tk.Button(root, text='Continue without signing in', command=self.close).pack(pady=5)
        self.later(100, self.drain)
        self.later(500, self.begin)

    def later(self, milliseconds, action):
        def run():
            self.timers.discard(timer)
            if not self.closed:
                action()
        timer = self.root.after(milliseconds, run)
        self.timers.add(timer)

    def label(self, text, size):
        return tk.Label(self.root, text=text, bg='#101816', fg='#b9f4d4', font=('DejaVu Sans', size))

    def submit(self, action, callback):
        generation = self.generation
        def finished(future):
            try:
                result, error = future.result(), None
            except Exception as exc:
                result, error = None, str(exc)
            self.events.put((generation, callback, result, error))
        self.worker.submit(action).add_done_callback(finished)

    def drain(self):
        while not self.events.empty():
            generation, callback, result, error = self.events.get_nowait()
            if not self.closed and generation == self.generation:
                callback(result, error)
        if not self.closed:
            self.later(100, self.drain)

    def begin(self):
        if self.busy:
            return
        self.busy = True
        self.generation += 1
        directory = self.directory.get()
        self.attempt = None
        self.qr.configure(image='')
        self.code.configure(text='')
        self.url.configure(text='')
        self.status.configure(text='Connecting to Dim…')
        def login():
            subprocess.run(['systemctl', '--user', 'start', 'sumos-dim.service'], check=True, timeout=15)
            with Client() as client:
                if self.remote_attempt:
                    client.call('account.login.cancel', {'providerId': PROVIDER, 'attemptId': self.remote_attempt})
                    self.remote_attempt = None
                status = client.call('account.status', {'providerId': PROVIDER})
                if status.get('account'):
                    return None
                result = client.call('account.login.begin', {'providerId': PROVIDER, 'directory': directory})
                self.remote_attempt = result['attemptId']
                return result
        self.submit(login, self.begun)

    def begun(self, result, error):
        self.busy = False
        if error:
            self.status.configure(text='Sign-in unavailable. Check your network and retry.')
            self.url.configure(text=error[:250])
        elif result is None:
            self.status.configure(text='Signed in. Open the agent to begin.')
        else:
            self.attempt = result['attemptId']
            url = result.get('verificationUriComplete') or result['verificationUri']
            parsed = urlsplit(url)
            if parsed.scheme != 'https' or not parsed.hostname or parsed.username:
                self.status.configure(text='Dim returned an unsafe verification URL.')
                return
            image = qrcode.make(url)
            image.thumbnail((200, 200), Image.Resampling.NEAREST)
            self.qr_image = ImageTk.PhotoImage(image)
            self.qr.configure(image=self.qr_image)
            self.code.configure(text=result['userCode'])
            self.url.configure(text=result['verificationUri'])
            self.status.configure(text='Scan to sign in. Use the displayed code if asked.')
            generation = self.generation
            self.later(2000, lambda: self.poll(generation))

    def poll(self, generation):
        if self.closed or generation != self.generation or not self.attempt:
            return
        attempt = self.attempt
        def status():
            with Client() as client:
                result = client.call('account.login.status', {'providerId': PROVIDER, 'attemptId': attempt})
                if result['status'] != 'pending':
                    self.remote_attempt = None
                return result
        self.submit(status, self.polled)

    def polled(self, result, error):
        if error:
            self.status.configure(text='Connection lost. Retry sign-in when the network returns.')
            return
        state = result['status']
        if state == 'pending':
            generation = self.generation
            self.later(2000, lambda: self.poll(generation))
            return
        self.attempt = None
        self.qr.configure(image='')
        self.code.configure(text='')
        self.url.configure(text='')
        self.status.configure(text={'completed': 'Signed in. Open the agent to begin.',
                                    'expired': 'Code expired. Retry to generate a new one.',
                                    'cancelled': 'Sign-in cancelled.', 'failed': 'Sign-in failed. Retry.'}[state])

    def open_agent(self):
        subprocess.Popen(['lxterminal', '-e', 'sumos-agent'])
        self.close()

    def network(self):
        subprocess.Popen(['nm-connection-editor'])

    def pause(self):
        self.generation += 1
        self.attempt = None
        self.busy = False
        def stop():
            subprocess.run(['systemctl', '--user', 'stop', 'sumos-dim.service'], check=True, timeout=20)
            self.remote_attempt = None
        self.submit(stop, lambda result, error: self.status.configure(
            text='Could not pause Dim.' if error else 'Dim stopped. Open agent or retry to resume.'))
        self.qr.configure(image='')
        self.code.configure(text='')
        self.url.configure(text='')

    def install_chrome(self):
        if messagebox.askyesno('Google Chrome terms',
                'Google Chrome is proprietary software. Review its terms at\n'
                'https://www.google.com/chrome/terms/\n\n'
                'Do you accept these terms and want to download and install Chrome?'):
            subprocess.Popen(['lxterminal', '-e', 'pkexec /usr/lib/sumos/install-chrome'])

    def close(self):
        if self.closed:
            return
        self.closed = True
        for timer in self.timers:
            self.root.after_cancel(timer)
        self.timers.clear()
        def cancel():
            if self.remote_attempt:
                try:
                    with Client() as client:
                        client.call('account.login.cancel', {'providerId': PROVIDER, 'attemptId': self.remote_attempt})
                except (OSError, RuntimeError):
                    pass
        self.worker.submit(cancel)
        self.worker.shutdown(wait=False, cancel_futures=False)
        self.root.destroy()


if __name__ == '__main__':
    app = tk.Tk()
    Welcome(app)
    app.mainloop()
