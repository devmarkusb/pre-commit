cmake_minimum_required(VERSION 3.21)
project(mb.pre-commit LANGUAGES NONE)

# Loaded via FetchContent_MakeAvailable: defines mb_pre_commit_setup() in the parent scope.
include("${CMAKE_CURRENT_SOURCE_DIR}/cmake/mb-pre-commit.cmake")

# Dogfood the hook when this tree is the top-level project. Skip when included via
# add_subdirectory/FetchContent so CMAKE_SOURCE_DIR is the consumer, not this path.
if(CMAKE_SOURCE_DIR STREQUAL CMAKE_CURRENT_SOURCE_DIR)
    mb_pre_commit_setup(
        PRE_COMMIT_INSTALL_EXAMPLE_CONFIG OFF
    )
endif()
