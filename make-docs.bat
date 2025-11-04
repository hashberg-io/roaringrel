call black roaringrel
cmd /c ./install-local.bat <nul
cd docs
call make api
call make clean
call make html
@pause
