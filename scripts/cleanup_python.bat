@echo off
setlocal
black .
ruff check . --fix
