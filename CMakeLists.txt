cmake_minimum_required(VERSION 3.21)
project(mb.pre-commit LANGUAGES NONE)

# Loaded via FetchContent_MakeAvailable: defines mb_pre_commit_setup() in the parent scope.
include("${CMAKE_CURRENT_SOURCE_DIR}/cmake/mb-pre-commit.cmake")

# Dogfood when this tree is the top-level project; skip when included via FetchContent.
mb_pre_commit_setup_project(PRE_COMMIT_INSTALL_EXAMPLE_CONFIG OFF)
