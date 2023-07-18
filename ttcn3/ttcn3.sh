#!/bin/sh -e
PROJECT="$1"
PROJECT_UPPER="$(echo "$PROJECT" | tr '[:lower:]' '[:upper:]')"
DIR_OSMODEV="$(readlink -f "$(dirname $0)/..")"
DIR_MAKE="${DIR_MAKE:-${DIR_OSMODEV}/ttcn3/make}"
DIR_OUTPUT="${DIR_OUTPUT:-${DIR_OSMODEV}/ttcn3/out}"
DIR_USR_LOCAL="$DIR_OSMODEV/ttcn3/usr_local"
JOBS="${JOBS:-9}"

# Osmocom libraries and programs relevant for the current testsuite will be
# built in this container. It must have all build dependencies available and
# be based on the same distribution that master-* containers are based on, so
# there are no incompatibilities with shared libraries.
DOCKER_IMG_BUILD="debian-bullseye-build"
DOCKER_IMG_TITAN="debian-bullseye-titan"

check_usage() {
	local name="$(basename $0)"
	if [ -z "$PROJECT" ]; then
		echo "usage: $name PROJECT"
		echo "examples:"
		echo "  * $name bsc"
		echo "  * $name bsc-sccplite"
		echo "  * $name hlr"
		exit 1
	fi
}

# Returns the name of the testsuite binary
get_testsuite_name() {
	case "$PROJECT" in
		bts-*) echo "BTS_Tests" ;;
		mgw) echo "MGCP_Test" ;;
		pcu-sns) echo "PCU_Tests" ;;
		*) echo "${PROJECT_UPPER}_Tests" ;;
	esac
}

get_testsuite_dir() {
	local hacks="${DIR_OSMODEV}/src/osmo-ttcn3-hacks"

	case "$PROJECT" in
		bsc-*) echo "$hacks/bsc" ;;
		bts-*) echo "$hacks/bts" ;;
		ggsn) echo "$hacks/ggsn_tests" ;;
		pcu-sns) echo "$hacks/pcu" ;;
		*) echo "$hacks/$PROJECT" ;;
	esac
}

get_testsuite_config() {
	case "$PROJECT" in
		bts-gprs) echo "BTS_Tests_GPRS.cfg" ;;
		bts-oml) echo "BTS_Tests_OML.cfg" ;;
		pcu-sns) echo "PCU_Tests_SNS.cfg" ;;
		*) echo "$(get_testsuite_name).cfg" ;;
	esac
}

get_testsuite_dir_docker() {
	local dp="${DIR_OSMODEV}/src/docker-playground"

	case "$PROJECT" in
		bsc-*)
			echo "$dp/ttcn3-bsc-test-$(echo "$PROJECT" | cut -d - -f 2-)"
			;;
		*)
			echo "$dp/ttcn3-$PROJECT-test"
			;;
	esac
}

get_testsuite_image() {
	case "$PROJECT" in
		bsc-*)
			echo "$USER/ttcn3-bsc-test"
			;;
		*)
			echo "$USER/ttcn3-$PROJECT-test"
			;;
	esac
}

# Dependencies not mentioned in all.deps
get_extra_libraries() {
	case "$PROJECT" in
		ggsn) echo "libgtpnl" ;;  # needed for --enable-gtp-linux
	esac
}

# Programs that need to be built
get_programs() {
	case "$PROJECT" in
		bsc|bsc-*) echo "osmo-stp osmo-bsc osmo-bts-omldummy" ;;
		bts) echo "osmo-bsc osmo-bts-trx" ;;
		msc) echo "osmo-stp osmo-msc" ;;
		pcu-sns) echo "osmo-pcu" ;;
		pcu) echo "osmo-pcu osmo-bsc osmo-bts-virtual" ;;
		sgsn) echo "osmo-stp osmo-sgsn" ;;
		sip) echo "osmo-sip-connector" ;;
		*) echo "osmo-$PROJECT" ;;
	esac
}

# Return the git repository name, which has the source for a specific program.
# $1: program name
get_program_repo() {
	case "$1" in
		osmo-bts-*) echo "osmo-bts" ;;
		osmo-pcap-*) echo "osmo-pcap" ;;
		osmo-stp) echo "libosmo-sccp" ;;
		*) echo "$1" ;;
	esac
}

check_ttcn3_install() {
	if ! command -v ttcn3_compiler > /dev/null; then
		echo "ERROR: ttcn3_compiler is not installed."
		echo "Install eclipse-titan from the Osmocom latest repository."
		echo "Details: https://osmocom.org/projects/cellular-infrastructure/wiki/Titan_TTCN3_Testsuites"
		exit 1
	fi
}

setup_dir_make() {
	cd "$DIR_OSMODEV"

	local docker_cmd="$DIR_OSMODEV/ttcn3/scripts/docker_configure_make.sh"
	docker_cmd="$docker_cmd $USER/$DOCKER_IMG_BUILD"

	./gen_makefile.py \
		default.opts \
		gtp_linux.opts \
		iu.opts \
		no_dahdi.opts \
		no_doxygen.opts \
		no_optimization.opts \
		no_systemd.opts \
		ttcn3/ttcn3.opts \
		werror.opts \
		--docker-cmd "$docker_cmd" \
		--make-dir "$DIR_MAKE" \
		--no-ldconfig \
		--no-make-check \
		--auto-distclean
}

# $1: name of repository (e.g. osmo-ttcn3-hacks)
clone_repo() {
	if ! [ -e "$DIR_OSMODEV/ttcn3/make/.make.${1}.clone" ]; then
		make -C "$DIR_MAKE" ".make.${1}.clone"
	fi
}

# Require testsuite dir and docker-playground dir
check_dir_testsuite() {
	local program
	local config_testsuite
	local dir_testsuite="$(get_testsuite_dir)"
	local dir_testsuite_docker="$(get_testsuite_dir_docker)"

	if ! [ -d "$dir_testsuite" ]; then
		echo "ERROR: project '$PROJECT' is invalid, resulting path not found: $dir_testsuite"
		exit 1
	fi

	if ! [ -d "$dir_testsuite_docker" ]; then
		echo "ERROR: could not find docker dir for project: $PROJECT: $dir_testsuite_docker"
		echo "Adjust get_testsuite_dir_docker?"
		exit 1
	fi

	# Sanity check for jenkins.sh
	if ! grep -q DOCKER_ARGS $dir_testsuite_docker/jenkins.sh; then
		echo "ERROR: DOCKER_ARGS not found in $dir_testsuite_docker/jenkins.sh!"
		exit 1
	fi
}

# Copy scripts from docker-playground to /usr/local/bin, so we don't miss them when mounting the outside /usr/local/bin
# inside the docker container
prepare_local_bin() {
	local scripts="
		${DIR_OSMODEV}/src/docker-playground/common/respawn.sh
		${DIR_OSMODEV}/src/docker-playground/common/ttcn3-docker-run.sh
	"

	for script in $scripts; do
		local script_path_localbin
		local name_install="$(basename "$script")"

		case "$name_install" in
			ttcn3-docker-run.sh) name_install="ttcn3-docker-run" ;;
		esac

		script_path_localbin="$DIR_USR_LOCAL/bin/$name_install"
		if [ -x "$script_path_localbin" ]; then
			continue
		fi

		install -v -Dm755 "$script" "$script_path_localbin"
	done
}

prepare_docker_build_container() {
	local dp="${DIR_OSMODEV}/src/docker-playground"

	if docker_image_exists "$USER/$DOCKER_IMG_BUILD"; then
		return
	fi

	echo "Building docker image: $USER/$DOCKER_IMG_BUILD"
	make -C "$dp/$DOCKER_IMG_BUILD"
}

prepare_docker_testsuite_container() {
	local testsuite_image="$(get_testsuite_image)"

	if docker_image_exists "$testsuite_image"; then
		return
	fi

	if ! docker_image_exists "$USER/$DOCKER_IMG_TITAN"; then
		echo "Building docker image: $USER/$DOCKER_IMG_TITAN"
		local dp="${DIR_OSMODEV}/src/docker-playground"
		make -C "$dp/$DOCKER_IMG_TITAN"
	fi

	echo "Building docker image: $testsuite_image"
	local testsuite_dir="$(get_testsuite_dir_docker)"
	make -C "$testsuite_dir"
}

# Use osmo-dev to build libraries not mentioned in all.deps, for example the
# libgtpnl dependency of osmo-ggsn that is only needed with --enable-gtp-linux.
build_extra_libraries() {
	local library
	local libraries="$(get_extra_libraries)"

	for library in $libraries; do
		set -x
		make -C "$DIR_MAKE" "$library"
		set +x
	done
}

# Use osmo-dev to build one Osmocom program and its dependencies
build_osmo_programs() {
	local program
	local programs="$(get_programs)"
	local make_args="-C $DIR_MAKE"

	for program in $programs; do
		local repo="$(get_program_repo "$program")"
		make_args="$make_args $repo"
	done

	set -x
	make $make_args
	set +x

	for program in $programs; do
		local repo="$(get_program_repo "$program")"
		local usr_local_bin="$DIR_USR_LOCAL/bin"

		if [ -z "$(find "$usr_local_bin" -name "$program")" ]; then
			echo "ERROR: program was not installed properly: $program"
			echo "Expected it to be in path: $PATH_dest"
			exit 1
		fi

		local reference="$DIR_MAKE/.make.$repo.build"
		if [ -z "$(find "$usr_local_bin" -name "$program" -newer "$reference")" ]; then
			echo "ERROR: $path is outdated!"
			echo "Maybe you need to pass a configure argument to $repo.git, so it builds and installs" \
				"$program?"
			exit 1
		fi
	done
}

docker_image_exists() {
	test -n "$(docker images -q "$1")"
}

build_testsuite() {
	cd "$(get_testsuite_dir)"

	local deps_marker="${DIR_OSMODEV}/ttcn3/make/.ttcn3-deps"
	if ! [ -e "$deps_marker" ]; then
		make -C "${DIR_OSMODEV}/src/osmo-ttcn3-hacks/deps" -j"$JOBS"
		touch "$deps_marker"
	fi

	# Build inside docker, so the resulting binary links against the
	# libraries available in docker and not the ones from the host system,
	# since we will run it inside docker later too.
	local hacks="${DIR_OSMODEV}/src/osmo-ttcn3-hacks"

	local testsuite_image="$(get_testsuite_image)"
	echo "testsuite_image: $testsuite_image"

	# -t: add a tty, so we get color output from the compiler
	docker run \
		--rm \
		-t \
		-v "$hacks:/osmo-ttcn3-hacks" \
		"$testsuite_image" \
		sh -exc "
			cd /osmo-ttcn3-hacks/$(basename "$(get_testsuite_dir)");
			./gen_links.sh;
			./regen_makefile.sh;
			make compile;
			make -j"$JOBS"
		"
}

run_docker() {
	local hacks="${DIR_OSMODEV}/src/osmo-ttcn3-hacks"
	local docker_dir="$(get_testsuite_dir_docker)"
	local docker_name="$(basename "$docker_dir")"
	local marker="${DIR_OSMODEV}/ttcn3/make/.docker.$docker_name.$IMAGE_SUFFIX"

	# Skip building docker containers if this already ran
	if [ -e "$marker" ]; then
		echo "NOTE: skipping docker container build, because marker exists: $marker"
		export NO_DOCKER_IMAGE_BUILD=1
	fi

	cd "$(get_testsuite_dir_docker)"
	export DOCKER_ARGS="\
		-e LD_LIBRARY_PATH=/usr/local/lib \
		-v "$DIR_USR_LOCAL":/usr/local:ro \
		-v $hacks:/osmo-ttcn3-hacks:ro \
		"
	export NO_LIST_OSMO_PACKAGES=1
	./jenkins.sh

	touch "$marker"
}

remove_old_logs() {
	sudo rm -rf /tmp/tmp.* 2>/dev/null
}

collect_logs() {
	# Merge and move logs
	cd /tmp/logs/*-tester

	# Format logs
	for log in *.merged; do
		ttcn3_logformat -o "${log}.log" "$log"
		sudo rm "$log"
	done

	# Print log path
	echo "---"
	echo "Logs: /tmp/logs"
	echo "---"
}

check_usage
check_ttcn3_install
setup_dir_make
clone_repo "osmo-ttcn3-hacks"
clone_repo "docker-playground"
check_dir_testsuite
prepare_local_bin
prepare_docker_build_container
build_extra_libraries
build_osmo_programs
prepare_docker_testsuite_container
build_testsuite
remove_old_logs
run_docker
collect_logs
