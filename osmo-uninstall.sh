#!/bin/sh -xe
# Remove all osmocom installations from given prefix, default is /usr/local
prefix="${1-/usr/local}"
echo "$prefix"
rm -rf $prefix/lib/libasn1c*
rm -rf $prefix/lib/libgtp.*
rm -rf $prefix/lib/libmtp.*
rm -rf $prefix/lib/libosmo*
rm -rf $prefix/lib/libsccp.*
rm -rf $prefix/lib/libsmpp34*
rm -rf $prefix/lib/libxua.a
rm -rf $prefix/lib/pkgconfig/libasn1c*
rm -rf $prefix/lib/pkgconfig/libgtp.*
rm -rf $prefix/lib/pkgconfig/libmtp.*
rm -rf $prefix/lib/pkgconfig/libosmo*
rm -rf $prefix/lib/pkgconfig/libsccp.*
rm -rf $prefix/lib/pkgconfig/libsmpp34*
rm -rf $prefix/include/asn1c/
rm -rf $prefix/include/gtp.h
rm -rf $prefix/include/gsn.h
rm -rf $prefix/include/gtpie.h
rm -rf $prefix/include/libgtpnl/
rm -rf $prefix/include/openbsc/
rm -rf $prefix/include/osmocom/
rm -rf $prefix/include/pdp.h
rm -rf $prefix/include/smpp34*
rm -rf $prefix/include/def_*
rm -rf $prefix/bin/abisip-find
rm -rf $prefix/bin/asn1c
rm -rf $prefix/bin/bs11_config
rm -rf $prefix/bin/crfc2asn1.pl
rm -rf $prefix/bin/enber
rm -rf $prefix/bin/ggsn
rm -rf $prefix/bin/ipaccess-config
rm -rf $prefix/bin/ipaccess-proxy
rm -rf $prefix/bin/isdnsync
rm -rf $prefix/bin/meas_json
rm -rf $prefix/bin/osmo-*
rm -rf $prefix/bin/sgsnemu
rm -rf $prefix/bin/unber
