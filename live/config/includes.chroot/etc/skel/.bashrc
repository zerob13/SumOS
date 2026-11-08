case $- in *i*) ;; *) return ;; esac
HISTCONTROL=ignoreboth
HISTSIZE=5000
shopt -s histappend checkwinsize
PS1='\[\e[32m\]\u@sumos\[\e[0m\]:\w\$ '
[ ! -r /usr/share/bash-completion/bash_completion ] || . /usr/share/bash-completion/bash_completion
alias ll='ls -lah --color=auto'
alias fd=fdfind
alias vi=nvim
export EDITOR=nvim
