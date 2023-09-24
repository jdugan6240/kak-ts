declare-option -hidden range-specs tree_sitter_ranges
declare-option -hidden range-specs tree_sitter_ranges_spare

declare-option -hidden bool tree_sitter_running false

declare-option -hidden str tree_sitter_dir %sh{echo $(dirname $kak_source)/../src}
declare-option -hidden str tree_sitter_cmd "python %opt{tree_sitter_dir}/main.py -s %val{session}"
declare-option -hidden str tree_sitter_req_fifo ""
declare-option -hidden str tree_sitter_buf_fifo ""

declare-option -hidden str tree_sitter_draft ""

# timestamp to debounce buffer change hooks.
declare-option -hidden str tree_sitter_timestamp

hook -always -group tree-sitter global KakEnd .* tree-sitter-quit

define-command -hidden tree-sitter-start %{
    nop %sh{
        if [ "$kak_opt_tree_sitter_running" = false ]; then
            # Start the kak-tree-sitter server
            (eval "${kak_opt_tree_sitter_cmd} -b '${kak_bufname}' -f ${kak_opt_filetype}") > /dev/null 2<&1 < /dev/null &
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
    nop %sh{
        printf '{
        "cmd": "stop"
        }' > $kak_opt_tree_sitter_req_fifo
    }
}

define-command tree-sitter-refresh %{
    evaluate-commands -no-hooks %sh{
        if [ "$kak_timestamp" != "$kak_opt_tree_sitter_timestamp" ]; then
            echo 'tree-sitter-parse-buffer'
            echo 'set-option buffer tree_sitter_timestamp %val{timestamp}'
        fi
    }
}

define-command tree-sitter-highlight-buffer %{
    nop %sh{
        printf '{
        "cmd": "highlight",
        "buf": "%s"
        }' "$kak_bufname" > $kak_opt_tree_sitter_req_fifo
    }
}

define-command tree-sitter-parse-buffer %{
    # First grab the buffer contents
    evaluate-commands -draft -no-hooks %{ execute-keys '%'; set-option buffer tree_sitter_draft %val{selection}}
    nop %sh{
        # Send the file contents to the file serving as kak-tree-sitter's buffer input
        printf "%s" "$kak_opt_tree_sitter_draft" > $kak_opt_tree_sitter_buf_fifo
        # Send the parse request
        printf '{
        "cmd": "parse",
        "buf": "%s"
        }' "$kak_bufname" > $kak_opt_tree_sitter_req_fifo
    }
}

define-command tree-sitter-new-buffer %{
    # Let kak-tree-sitter know of the new buffer
    nop %sh{
        printf '{
        "cmd": "new",
        "name": "%s",
        "lang": "%s"
        }' "$kak_bufname" "$kak_opt_filetype" > $kak_opt_tree_sitter_req_fifo
    }
}
