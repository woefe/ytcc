set -l cmd "ytcc"
set -l channel '__fish_contains_opt -s r -s f channel-filter delete-channel'
set -l video '__fish_contains_opt -s w -s d -s m watch download mark-watched'

function __ytcc_last_flag
    set -l tokens (commandline -poc)
    for token in $tokens
        if test (echo $token | head -c 1) = "-"
            set last_flag $token
        end
    end

    for arg in $argv
        if test "x$last_flag" = "x$arg"
            return 0
        end
    end
    return 1
end

complete -c $cmd -x    -l help            -s h -d "show help message and exit"
complete -c $cmd -f -r -l add-channel     -s a -d "add a new channel"
complete -c $cmd -f    -l list-channels   -s c -d "print all subscribed channels"
complete -c $cmd -f    -l delete-channel  -s r -d "unsubscribe from channels"
complete -c $cmd -f    -l update          -s u -d "update the videolist"
complete -c $cmd -f    -l list-unwatched  -s l -d "print all of unwatched videos"
complete -c $cmd -f    -l watch           -s w -d "play videos"
complete -c $cmd -f    -l download        -s d -d "download the videos"
complete -c $cmd -f    -l mark-watched    -s m -d "mark videos as watched"
complete -c $cmd -f    -l channel-filter  -s f -d "apply a channel filter"
complete -c $cmd -f    -l include-watched -s n -d "apply include-watched filter"
complete -c $cmd -f -r -l since           -s s -d "apply date begin filter"
complete -c $cmd -f -r -l to              -s t -d "apply date end filter"
complete -c $cmd -f -r -l search          -s q -d "search for a given pattern"
complete -c $cmd    -r -l path            -s p -d "set the download path"
complete -c $cmd -f    -l no-description  -s g -d "do not print the video description"
complete -c $cmd -f -r -l columns         -s o -d "column" -a 'ID Date Channel Title URL'
complete -c $cmd -f    -l no-header            -d "don't print table header"
complete -c $cmd -f    -l no-video        -s x -d "audio only"
complete -c $cmd -f    -l yes             -s y -d "automatically answer all questions with yes"
complete -c $cmd    -r -l import-from     -s y -d "import subscriptions from youtube"
complete -c $cmd -x    -l cleanup              -d "cleanup and shrink database file"
complete -c $cmd -x    -l version         -s v -d "output version information and exit"

complete -c $cmd -f -n '__ytcc_last_flag -r --delete-channel -f --channel-filter' -a "(ytcc --list-channels)"
complete -c $cmd -f -n '__ytcc_last_flag -w --watch -d --download -m --mark' -a "(ytcc -lo ID --no-header | tr -d ' ')"
complete -c $cmd -f -n '__ytcc_last_flag -o --columns' -a 'ID Date Channel Title URL'
