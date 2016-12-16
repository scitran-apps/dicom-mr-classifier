#!/bin/bash
# Exports the container in the cwd.
# The container can be exported once it's started with

version=0.1.8
container=dicom-mr-classifier
outname=$container-$version.tar
image=scitran/$container


# Check if outname was passed in.
if [[ -n $1 ]]; then
    outname=$1
fi

docker run --name=$container --entrypoint=/bin/true $image
docker export -o $outname $container
docker rm $container
