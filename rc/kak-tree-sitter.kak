declare-option -hidden range-specs tree_sitter_ranges

declare-option -hidden bool tree_sitter_running false

declare-option -hidden str tree_sitter_dir %sh{echo $(dirname $kak_source)/..}
declare-option -hidden str tree_sitter_args ""
declare-option -hidden str tree_sitter_req_fifo ""
declare-option -hidden str tree_sitter_buf_fifo ""

# timestamp to debounce buffer change hooks.
declare-option -hidden str tree_sitter_timestamp

hook -always -group tree-sitter global KakEnd .* tree-sitter-quit

define-command -hidden tree-sitter-start %{
    nop %sh{
        if [ "$kak_opt_tree_sitter_running" = false ]; then
            # Start the kak-tree-sitter server
            # Using the venv python directly since it's faster than using poetry,
            # and we need as quick a start time as possible
            ($kak_opt_tree_sitter_dir/.venv/bin/python $kak_opt_tree_sitter_dir/src/main.py -s $kak_session -b "${kak_bufname}" -f ${kak_opt_filetype} ${kak_opt_tree_sitter_args}) > /dev/null 2<&1 < /dev/null &
        fi
    }

    remove-hooks buffer tree-sitter

    try %{
        add-highlighter buffer/ ranges tree_sitter_ranges
    }
}

define-command -hidden tree-sitter-started %{
    remove-hooks buffer tree-sitter

    tree-sitter-new-buffer

    try %{
        add-highlighter buffer/ ranges tree_sitter_ranges
    }
}

define-command tree-sitter-enable-buffer %{
    echo -debug %val{bufname}
    echo -debug %opt{filetype}
    evaluate-commands %sh{
        if [ "$kak_opt_tree_sitter_running" = false ]; then
            printf "%s\n" "tree-sitter-start"
        else
            printf "%s\n" "tree-sitter-started"
        fi
    }
}

define-command -hidden tree-sitter-buffer-ready %{
    hook -group tree-sitter buffer InsertIdle .* tree-sitter-refresh
    hook -group tree-sitter buffer NormalIdle .* tree-sitter-refresh
    hook -group tree-sitter buffer BufReload .* tree-sitter-refresh

    tree-sitter-refresh
}


define-command -hidden tree-sitter-quit %{
    # Stop the kak-tree-sitter server
    echo -to-file %opt{tree_sitter_req_fifo} -- "{""cmd"": ""stop""}"
    # nop %sh{
    #     printf '{
    #         "cmd": "stop"
    #     }' > $kak_opt_tree_sitter_req_fifo
    # }
}

define-command tree-sitter-refresh %{
    evaluate-commands -no-hooks %sh{
        if [ "$kak_timestamp" != "$kak_opt_tree_sitter_timestamp" ]; then
            echo 'tree-sitter-parse-buffer'
            echo 'set-option buffer tree_sitter_timestamp %val{timestamp}'
        fi
    }
}

define-command -hidden tree-sitter-parse-buffer %{
    # Write the contents of the buffer
    write -force %opt{tree_sitter_buf_fifo}

    # Issue the parse command
    echo -to-file %opt{tree_sitter_req_fifo} -- "{""cmd"": ""parse"", ""buf"": ""%val{bufname}""}"
}

define-command -hidden tree-sitter-new-buffer %{
    # Let kak-tree-sitter know of the new buffer
    echo -to-file %opt{tree_sitter_req_fifo} -- "{""cmd"": ""new"", ""name"": ""%val{bufname}"", ""lang"": ""%opt{filetype}""}"
}
