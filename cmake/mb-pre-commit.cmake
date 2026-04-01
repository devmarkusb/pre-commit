include_guard(GLOBAL)

# Directory of this list file (cmake/). For CMake < 3.17, mb_pre_commit_setup() falls back to this.
# Do not derive from CMAKE_CURRENT_LIST_FILE: in some FetchContent layouts its DIRECTORY is empty,
# which breaks paths like ${_dir}/pre-commit.in -> /pre-commit.in.
set(_MB_PRE_COMMIT_CMAKE_DIR "${CMAKE_CURRENT_LIST_DIR}")

function(mb_pre_commit_setup)
    set(options)
    set(oneValueArgs
        PROJECT_SOURCE_DIR
        PROJECT_BINARY_DIR
        PRE_COMMIT_MODE
        PRE_COMMIT_VERSION
        PRE_COMMIT_VENV_DIR
        PRE_COMMIT_INSTALL_EXAMPLE_CONFIG
        PRE_COMMIT_SWEEP_TARGET
    )
    cmake_parse_arguments(PC "${options}" "${oneValueArgs}" "" ${ARGN})

    if(NOT PC_PROJECT_SOURCE_DIR)
        set(PC_PROJECT_SOURCE_DIR "${CMAKE_SOURCE_DIR}")
    endif()

    if(NOT PC_PROJECT_BINARY_DIR)
        set(PC_PROJECT_BINARY_DIR "${CMAKE_BINARY_DIR}")
    endif()

    if(NOT PC_PRE_COMMIT_MODE)
        set(PC_PRE_COMMIT_MODE "CUSTOM")
    endif()

    if(NOT PC_PRE_COMMIT_VERSION)
        set(PC_PRE_COMMIT_VERSION "4.5.1")
    endif()

    if(NOT PC_PRE_COMMIT_VENV_DIR)
        set(PC_PRE_COMMIT_VENV_DIR "${PC_PROJECT_SOURCE_DIR}/.venv")
    endif()

    if(NOT DEFINED PC_PRE_COMMIT_INSTALL_EXAMPLE_CONFIG)
        set(PC_PRE_COMMIT_INSTALL_EXAMPLE_CONFIG ON)
    endif()

    if(NOT DEFINED PC_PRE_COMMIT_SWEEP_TARGET)
        set(PC_PRE_COMMIT_SWEEP_TARGET "mb-pre-commit-sweep")
    endif()

    if(NOT IS_ABSOLUTE "${PC_PROJECT_SOURCE_DIR}")
        get_filename_component(
            PC_PROJECT_SOURCE_DIR
            "${PC_PROJECT_SOURCE_DIR}"
            ABSOLUTE
            BASE_DIR "${CMAKE_SOURCE_DIR}"
        )
    endif()

    if(NOT IS_ABSOLUTE "${PC_PROJECT_BINARY_DIR}")
        get_filename_component(
            PC_PROJECT_BINARY_DIR
            "${PC_PROJECT_BINARY_DIR}"
            ABSOLUTE
            BASE_DIR "${CMAKE_BINARY_DIR}"
        )
    endif()

    if(NOT IS_ABSOLUTE "${PC_PRE_COMMIT_VENV_DIR}")
        get_filename_component(
            PC_PRE_COMMIT_VENV_DIR
            "${PC_PRE_COMMIT_VENV_DIR}"
            ABSOLUTE
            BASE_DIR "${PC_PROJECT_SOURCE_DIR}"
        )
    endif()

    find_package(Python3 REQUIRED COMPONENTS Interpreter)

    # Inside function(), CMAKE_CURRENT_LIST_DIR is the caller's file — use the directory of
    # this module's list file (CMake 3.17+), else file-scope _MB_PRE_COMMIT_CMAKE_DIR.
    if(CMAKE_VERSION VERSION_GREATER_EQUAL "3.17")
        set(_tool_module_dir "${CMAKE_CURRENT_FUNCTION_LIST_DIR}")
    else()
        set(_tool_module_dir "${_MB_PRE_COMMIT_CMAKE_DIR}")
    endif()

    set(_configs_root "${_tool_module_dir}/../configs")
    set(_hook_template "${_tool_module_dir}/pre-commit.in")
    get_filename_component(
        _setup_script
        "${_tool_module_dir}/../python/mb-pre-commit-setup.py"
        ABSOLUTE
    )

    if(NOT EXISTS "${_setup_script}")
        message(
            FATAL_ERROR
            "mb_pre_commit_setup: setup script not found: ${_setup_script}"
        )
    endif()

    # Re-run configure if the hook template or shipped example configs change.
    set_property(
        DIRECTORY
        APPEND
        PROPERTY CMAKE_CONFIGURE_DEPENDS "${_hook_template}" "${_setup_script}"
    )
    # CONFIGURE_DEPENDS registers these files with the build tool so CMake re-runs when
    # they change. Do not also append them to CMAKE_CONFIGURE_DEPENDS — that duplicates
    # the same outputs in Ninja ("defined as an output multiple times").
    # The GLOB list is unused on purpose; only CONFIGURE_DEPENDS side effects matter.
    file(
        GLOB_RECURSE _example_config_deps_unused
        CONFIGURE_DEPENDS
        "${_configs_root}/v*/.pre-commit-config.yaml"
        "${_configs_root}/v*/.markdownlint.yaml"
    )

    set(_setup_args
        "${Python3_EXECUTABLE}"
        "${_setup_script}"
        --project-source-dir
        "${PC_PROJECT_SOURCE_DIR}"
        --project-binary-dir
        "${PC_PROJECT_BINARY_DIR}"
        --mode
        "${PC_PRE_COMMIT_MODE}"
        --version
        "${PC_PRE_COMMIT_VERSION}"
        --venv-dir
        "${PC_PRE_COMMIT_VENV_DIR}"
        --tool-root
        "${_tool_module_dir}"
        --python
        "${Python3_EXECUTABLE}"
    )
    if(NOT PC_PRE_COMMIT_INSTALL_EXAMPLE_CONFIG)
        list(APPEND _setup_args --no-install-example-config)
    endif()

    execute_process(COMMAND ${_setup_args} RESULT_VARIABLE _mb_pc_setup_result)
    if(NOT _mb_pc_setup_result EQUAL 0)
        message(
            FATAL_ERROR
            "mb_pre_commit_setup: mb-pre-commit-setup.py failed (exit ${_mb_pc_setup_result})"
        )
    endif()

    if(WIN32)
        set(_venv_python "${PC_PRE_COMMIT_VENV_DIR}/Scripts/python.exe")
    else()
        set(_venv_python "${PC_PRE_COMMIT_VENV_DIR}/bin/python3")
    endif()

    # One-word build target: pre-commit on the whole tree (not just staged files).
    if(NOT PC_PRE_COMMIT_SWEEP_TARGET STREQUAL "OFF")
        set(_sweep_target "${PC_PRE_COMMIT_SWEEP_TARGET}")
        if(TARGET "${_sweep_target}")
            if(_sweep_target STREQUAL "mb-pre-commit-sweep")
                set(_sweep_target mb_pre_commit_sweep)
                message(
                    STATUS
                    "mb_pre_commit_setup: target 'mb-pre-commit-sweep' already exists; using 'mb_pre_commit_sweep' (pre-commit run --all-files)"
                )
            endif()
        endif()
        if(TARGET "${_sweep_target}")
            message(
                FATAL_ERROR
                "mb_pre_commit_setup: PRE_COMMIT_SWEEP_TARGET name '${_sweep_target}' is already a target"
            )
        endif()

        add_custom_target(
            "${_sweep_target}"
            COMMAND "${_venv_python}" -m pre_commit run --all-files
            WORKING_DIRECTORY "${PC_PROJECT_SOURCE_DIR}"
            COMMENT "pre-commit: all files"
            USES_TERMINAL
        )
        message(
            STATUS
            "pre-commit sweep: cmake --build <dir> --target ${_sweep_target}  (pre-commit run --all-files)"
        )
    endif()
endfunction()
