#!/bin/sh -ex
# Passed by ttcn3.sh to gen_makefile.py to run './configure', 'make' and
# 'make install' inside docker. The osmo-dev directory is mounted at the same
# location inside the docker container. A usr_local dir is mounted to
# /usr/local, so 'make install' can put all files there and following builds
# have the files available.
DIR_OSMODEV="$(readlink -f "$(dirname $0)/../..")"
DIR_MAKE="$DIR_OSMODEV/ttcn3/make"
DIR_USR_LOCAL="$DIR_OSMODEV/ttcn3/usr_local"
RUN_SCRIPT="$DIR_OSMODEV/ttcn3/.run.sh"
DOCKER_IMG="$1"
UID="$(id -u)"
shift

mkdir -p "$DIR_MAKE"

# Script running as user inside docker
echo "#!/bin/sh -ex" > "$RUN_SCRIPT"
echo "cd \"$PWD\"" >> "$RUN_SCRIPT"
for i in "$@"; do
	echo -n "'$i' " >> "$RUN_SCRIPT"
done
echo >> "$RUN_SCRIPT"
chmod +x "$RUN_SCRIPT"

docker run \
	--rm \
	-e "LD_LIBRARY_PATH=/usr/local/lib" \
	-v "$DIR_OSMODEV:$DIR_OSMODEV" \
	-v "$DIR_USR_LOCAL:/usr/local" \
	-v "$RUN_SCRIPT:/tmp/run.sh:ro" \
	"$DOCKER_IMG" \
	sh -ex -c "
		if ! id -u $UID 2>/dev/null; then
			useradd -u $UID user
		fi
		su \$(id -un $UID) -c /tmp/run.sh
	"
