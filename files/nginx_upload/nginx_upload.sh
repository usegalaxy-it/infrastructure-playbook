!#/usr/bin/bash
#wget https://nginx.org/download/nginx-$1.tar.gz
nginx_url="https://nginx.org/download/nginx-$1.tar.gz"
nginx_module_url="https://github.com/fdintino/nginx-upload-module/archive/$2.tar.gz"
version_nginx=$1
version_module=$2
mkdir nginx_temp
cd nginx_temp
wget -nc $nginx_url
wget -nc $nginx_module_url
tar -xvf $(basename $nginx_url)
tar -xvf $( basename $nginx_module_url)
cd nginx-$version_nginx
nginx -V |& awk -v var=$version_module -F "configure arguments:" '{ print $2 " --add-dynamic-module=../nginx-upload-module-"var }' | xargs ./configure
make modules

sudo cp objs/ngx_http_upload_module.so  /usr/lib64/nginx/modules/
cd -
cd .. && rm -rf nginx_temp
