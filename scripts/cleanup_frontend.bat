@echo off
setlocal
npx prettier --write "frontend/**/*.html" "frontend/assets/css/**/*.css" "frontend/assets/js/**/*.js" ".prettierrc" ".eslintrc.json"
npx eslint frontend/assets/js --fix
