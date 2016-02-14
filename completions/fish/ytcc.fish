set -l cmd "ytcc"
set -l channel '__fish_contains_opt -s r -s f channel-filter delete-channel'
set -l video '__fish_contains_opt -s w -s d -s m watch download mark-watched'

complete -c $cmd -f -l add-channel     -s a -d "add a new channel"
complete -c $cmd -x -l help            -s h -d "show help message and exit"
complete -c $cmd -f -l list-channels   -s c -d "print all subscribed channels"
complete -c $cmd -f -l list-recent     -s n -d "print all videos that were recently added"
complete -c $cmd -f -l list-unwatched  -s l -d "print all of unwatched videos"
complete -c $cmd -f -l no-description  -s g -d "do not print the video description"
complete -c $cmd    -l path            -s p -d "set the download path"
complete -c $cmd -f -l update          -s u -d "update the videolist"
complete -c $cmd -x -l version         -s v -d "output version information and exit"
complete -c $cmd -f -l yes             -s y -d "automatically answer all questions with yes"
complete -c $cmd -f -l watch           -s w -d "play videos"
complete -c $cmd -f -l download        -s d -d "download the videos"
complete -c $cmd -f -l mark-watched    -s m -d "mark videos as watched"
complete -c $cmd -f -l channel-filter  -s f -d "apply a filter"
complete -c $cmd -f -l delete-channel  -s r -d "unsubscribe from a channel"

complete -c $cmd -f -n $channel -a "(ytcc --list-channels)"
complete -c $cmd -f -n $video -a "(ytcc --list-unwatched | cut -f1 -d' ')"
