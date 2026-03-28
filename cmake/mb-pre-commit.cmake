include_guard(GLOBAL)

function(mb_pre_commit_setup)
    set(options)
    set(oneValueArgs
        PROJECT_SOURCE_DIR
        PROJECT_BINARY_DIR
        PRE_COMMIT_MODE
        PRE_COMMIT_VERSION
        PRE_COMMIT_VENV_DIR
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

    find_package(Git QUIET)
    find_package(Python3 REQUIRED COMPONENTS Interpreter)

    set(_tool_module_dir "${CMAKE_CURRENT_LIST_DIR}")
    set(_hook_template "${_tool_module_dir}/pre-commit.in")
    set(_generated_hook "${PC_PROJECT_BINARY_DIR}/pre-commit")

    set(_git_dir "${PC_PROJECT_SOURCE_DIR}/.git")
    set(_git_hooks_dir "${_git_dir}/hooks")
    set(_hook_target "${_git_hooks_dir}/pre-commit")

    if(WIN32)
        set(_venv_python "${PC_PRE_COMMIT_VENV_DIR}/Scripts/python.exe")
    else()
        set(_venv_python "${PC_PRE_COMMIT_VENV_DIR}/bin/python3")
    endif()

    if(NOT GIT_FOUND OR NOT EXISTS "${_git_dir}" OR NOT EXISTS "${_git_hooks_dir}")
        message(STATUS "Git checkout not detected in ${PC_PROJECT_SOURCE_DIR}; skipping pre-commit setup")
        return()
    endif()

    if(NOT EXISTS "${_hook_template}")
        message(FATAL_ERROR "mb_pre_commit_setup: hook template not found: ${_hook_template}")
    endif()

    if(NOT PC_PRE_COMMIT_MODE STREQUAL "CUSTOM" AND NOT PC_PRE_COMMIT_MODE STREQUAL "NATIVE")
        message(FATAL_ERROR "mb_pre_commit_setup: invalid PRE_COMMIT_MODE='${PC_PRE_COMMIT_MODE}', expected CUSTOM or NATIVE")
    endif()

    # Re-run configure if the hook template changes.
    set_property(
        DIRECTORY APPEND PROPERTY
        CMAKE_CONFIGURE_DEPENDS
        "${_hook_template}"
    )

    # Forward-slash path works better in generated shell script, including Git Bash on Windows.
    file(TO_CMAKE_PATH "${_venv_python}" PRE_COMMIT_VENV_PYTHON_FOR_HOOK)

    configure_file(
        "${_hook_template}"
        "${_generated_hook}"
        @ONLY
    )

    if(NOT EXISTS "${_venv_python}")
        message(STATUS "Creating Python virtual environment for pre-commit: ${PC_PRE_COMMIT_VENV_DIR}")
        execute_process(
            COMMAND "${Python3_EXECUTABLE}" -m venv "${PC_PRE_COMMIT_VENV_DIR}"
            RESULT_VARIABLE _venv_result
        )
        if(NOT _venv_result EQUAL 0)
            message(FATAL_ERROR "Failed to create Python virtual environment: ${PC_PRE_COMMIT_VENV_DIR}")
        endif()
    endif()

    set(_install_pre_commit TRUE)
    execute_process(
        COMMAND "${_venv_python}" -m pre_commit --version
        OUTPUT_VARIABLE _pc_version_out
        ERROR_VARIABLE _pc_version_err
        RESULT_VARIABLE _pc_version_res
        OUTPUT_STRIP_TRAILING_WHITESPACE
        ERROR_STRIP_TRAILING_WHITESPACE
    )

    if(_pc_version_res EQUAL 0)
        string(REGEX MATCH "[0-9]+\\.[0-9]+\\.[0-9]+"
            _installed_version
            "${_pc_version_out}"
        )
        if(_installed_version STREQUAL "${PC_PRE_COMMIT_VERSION}")
            set(_install_pre_commit FALSE)
        endif()
    endif()

    if(_install_pre_commit)
        message(STATUS "Installing pre-commit ${PC_PRE_COMMIT_VERSION} into ${PC_PRE_COMMIT_VENV_DIR}")
        execute_process(
            COMMAND "${_venv_python}" -m pip install --upgrade
            pip
            "pre-commit==${PC_PRE_COMMIT_VERSION}"
            RESULT_VARIABLE _pip_result
        )
        if(NOT _pip_result EQUAL 0)
            message(FATAL_ERROR "Failed to install pre-commit ${PC_PRE_COMMIT_VERSION}")
        endif()
    else()
        message(STATUS "pre-commit ${PC_PRE_COMMIT_VERSION} already available in ${PC_PRE_COMMIT_VENV_DIR}")
    endif()

    if(PC_PRE_COMMIT_MODE STREQUAL "CUSTOM")
        file(COPY_FILE
            "${_generated_hook}"
            "${_hook_target}"
            ONLY_IF_DIFFERENT
        )

        if(NOT WIN32)
            file(CHMOD
                "${_hook_target}"
                PERMISSIONS
                OWNER_READ OWNER_WRITE OWNER_EXECUTE
                GROUP_READ GROUP_EXECUTE
                WORLD_READ WORLD_EXECUTE
            )
        endif()

        message(STATUS "Installed custom pre-commit hook: ${_hook_target}")

    elseif(PC_PRE_COMMIT_MODE STREQUAL "NATIVE")
        execute_process(
            COMMAND "${_venv_python}" -m pre_commit install --install-hooks --hook-type pre-commit
            WORKING_DIRECTORY "${PC_PROJECT_SOURCE_DIR}"
            RESULT_VARIABLE _install_result
        )
        if(NOT _install_result EQUAL 0)
            message(FATAL_ERROR "pre-commit install failed")
        endif()

        message(STATUS "Installed native pre-commit hook in ${PC_PROJECT_SOURCE_DIR}")
    endif()
endfunction()
