#!/bin/sh -ex
# Passed by ttcn3.sh to gen_makefile.py to run './configure', 'make' and
# 'make install' inside docker. The osmo-dev directory is mounted at the same
# location inside the docker container. A usr_local dir is mounted to
# /usr/local, so 'make install' can put all files there and following builds
# have the files available.
# env vars: OSMODEV_PROJECT
DIR_OSMODEV="$(readlink -f "$(dirname $0)/../..")"
DIR_MAKE="$DIR_OSMODEV/ttcn3/make"
DIR_USR_LOCAL="$DIR_OSMODEV/ttcn3/usr_local"
DIR_VAR_LOCAL="$DIR_OSMODEV/ttcn3/var_local"
DIR_CCACHE="$DIR_OSMODEV/ttcn3/ccache/osmocom-programs"
RUN_SCRIPT="$DIR_OSMODEV/ttcn3/.run.sh"
UID="$(id -u)"

# Osmocom libraries and programs relevant for the current testsuite will be
# built in this container. It must have all build dependencies available and
# be based on the same distribution that master-* containers are based on, so
# there are no incompatibilities with shared libraries.
DOCKER_IMG_BUILD="debian-bookworm-build"
DOCKER_IMG_BUILD_OGS="open5gs-master"

docker_image_exists() {
	test -n "$(docker images -q "$1")"
}

build_docker_img() {
	local img="$1"
	local dp="${DIR_OSMODEV}/src/docker-playground"

	if ! docker_image_exists "$USER/$img"; then
		echo "Building docker image: $USER/$img"
		make -C "$dp/$img"
	fi
}

build_docker_imgs() {
	build_docker_img "$DOCKER_IMG_BUILD"

	if [ "$OSMODEV_PROJECT" = "open5gs" ]; then
		build_docker_img "$DOCKER_IMG_BUILD_OGS"
	fi
}

set_docker_img_var() {
	case "$OSMODEV_PROJECT" in
	open5gs)
		DOCKER_IMG="$USER/$DOCKER_IMG_BUILD_OGS"
		;;
	*)
		DOCKER_IMG="$USER/$DOCKER_IMG_BUILD"
		;;
	esac
}

mkdir -p \
	"$DIR_MAKE" \
	"$DIR_CCACHE" \
	"$DIR_USR_LOCAL" \
	"$DIR_VAR_LOCAL"

# Script running as user inside docker
echo "#!/bin/sh -ex" > "$RUN_SCRIPT"
echo "cd \"$PWD\"" >> "$RUN_SCRIPT"
for i in "$@"; do
	echo -n "'$i' " >> "$RUN_SCRIPT"
done
echo >> "$RUN_SCRIPT"
chmod +x "$RUN_SCRIPT"

build_docker_imgs
set_docker_img_var

docker run \
	--rm \
	-t \
	-e "LD_LIBRARY_PATH=/usr/local/lib" \
	-v "$DIR_OSMODEV:$DIR_OSMODEV" \
	-v "$DIR_USR_LOCAL:/usr/local" \
	-v "$DIR_VAR_LOCAL:/var/local" \
	-v "$RUN_SCRIPT:/tmp/run.sh:ro" \
	-v "$DIR_CCACHE:/home/build/.ccache" \
	"$DOCKER_IMG" \
	sh -ex -c "
		if ! id -u $UID 2>/dev/null; then
			useradd -u $UID user
		fi
		su \$(id -un $UID) -c /tmp/run.sh
	"
