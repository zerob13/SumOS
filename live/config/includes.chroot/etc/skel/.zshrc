autoload -Uz compinit && compinit
HISTFILE=~/.zsh_history
HISTSIZE=5000
SAVEHIST=5000
setopt HIST_IGNORE_SPACE HIST_IGNORE_DUPS SHARE_HISTORY
PROMPT='%F{green}%n@sumos%f:%~%# '
bindkey -e
alias ll='ls -lah --color=auto'
alias fd=fdfind
alias vi=nvim
export EDITOR=nvim
