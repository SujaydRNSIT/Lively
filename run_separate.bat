@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Lively Voice AI - Separate Windows
call run.bat --windows %*
exit /b %errorlevel%
