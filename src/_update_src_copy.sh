#!/bin/sh -e
# Update the src_copy dir with all relevant files from the original git
# repository (+ submodules). Used by gen_makefile.py --autoreconf-in-src-copy.

update_git_dir() {
	local src="$1"
	local dest="$DEST_DIR_PROJ/$(echo "$src" | cut -c 3-)"  # cut: remove './'

	echo "updating src_copy: $dest"

	# Get list of files (everything that is not in gitignore)
	git \
		-C "$src" \
		ls-files \
		--others \
		--cached \
		--exclude-standard \
		> "$COPY_LIST"

	mkdir -p "$dest"

	# Copy files that changed
	rsync \
		--archive \
		--files-from="$COPY_LIST" \
		"$src" \
		"$dest"
}

# The "git-version-gen" script only works correctly when running inside a git
# repository. Run it in the original git repo and copy its output to
# ".tarball-version", so when configure.ac runs it again the version gets read
# from there.
run_git_version_gen() {
	if ! [ -e "$src/git-version-gen" ]; then
		return
	fi

	local version_file="$DEST_DIR_PROJ/$src/.tarball-version"
	rm -f "$version_file"

	# git-version-gen does not run without the tarball-version argument
	version_new="$(cd "$src" && ./git-version-gen "$version_file")"

	echo "updating version: $version_new"
	echo "$version_new" >"$version_file"
}

update_git_dirs_all() {
	local git_dirs="$(find . -name '.git')"

	if [ -z "$git_dirs" ]; then
		echo "_update_read_only_src_copy: find failed"
		exit 1
	fi

	for git_dir in $git_dirs; do
		local src="$(dirname "$git_dir")"
		update_git_dir "$src"
		run_git_version_gen "$src"
	done
}

# Some project are symlinks to a path in another git repository (for example
# osmocom-bb_layer23 -> osmocom-bb/src/host/layer23). For those we need to
# add such a symlink to the src_copy dir and then run _update_src_copy.sh on
# the main project (osmocom-bb in the example).
handle_symlink_proj() {
	local linkdest
	local git_topdir
	local proj_main
	local relpath

	if ! [ -L "$SRC_DIR/$PROJ" ]; then
		return
	fi

	linkdest="$(realpath "$SRC_DIR/$PROJ")"
	git_topdir="$(cd "$linkdest" && git rev-parse --show-toplevel)"

	if [ -z "$git_topdir" ]; then
		"_update_src_copy: getting git topdir failed: $linkdest"
		exit 1
	fi

	proj_main="$(basename "$git_topdir")"

	# Create the symlink in src_copy
	if ! [ -L "$DEST_DIR_PROJ" ]; then
		relpath="$(realpath -s --relative-to="$git_topdir" "$linkdest")"
		if [ -z "$relpath" ]; then
			"_update_src_copy: getting relpath failed: $linkdest"
			exit 1
		fi
		ln -s "$proj_main/$relpath" "$DEST_DIR_PROJ"
	fi

	# Copy the original project files to src_copy
	exec sh -e "$0" "$SRC_DIR" "$proj_main" "$TIME_START"
	# Not continuing below (exec)
}

MAKE_DIR="$PWD"
SRC_DIR="$1"
PROJ="$2"
TIME_START="$3"
MARKER="$MAKE_DIR/.make.$PROJ.src_copy"

# Don't run more than once per "make" call
if [ "$(cat "$MARKER" 2>/dev/null)" = "$TIME_START" ]; then
	exit 0
fi

DEST_DIR_PROJ="$MAKE_DIR/src_copy/$PROJ"
handle_symlink_proj

COPY_LIST="$(mktemp --suffix=-osmo-dev-rsync-copylist)"

cd "$SRC_DIR/$PROJ"
update_git_dirs_all
rm "$COPY_LIST"
echo "$TIME_START" >"$MARKER"

# Output an empty line when done to make the Makefile output more readable
echo
