#!/usr/bin/env python2.3

"""
Read a MAF from stdin and break into a set of mafs containing 
no more than a certain number of columns
"""

usage = "usage: %prog"

import sys, string
import bx.align.maf
from optparse import OptionParser

import psyco_full

INF="inf"

def __main__():

    # Parse command line arguments

    parser = OptionParser( usage=usage )
    parser.add_option( "-o", "--outprefix", action="store", default="" )
    parser.add_option( "-c", "--component", action="store", default=None )
    ( options, args ) = parser.parse_args()

    out_prefix = options.outprefix
    comp = options.component
    if comp is not None:
       comp = int( comp )

    maf_reader = bx.align.maf.Reader( sys.stdin )

    writers = {}

    for m in maf_reader:
       
        if comp is None: 
            writer_key = string.join( [ c.src for c in m.components ], '_' )
        else:
            writer_key = m.components[ comp ].src

        if not writers.has_key( writer_key ):
            writer = bx.align.maf.Writer( file( "%s%s.maf" % ( out_prefix, writer_key ), "w" ) )
            writers[ writer_key ] = writer
        else:
            writer = writers[ writer_key ] 

        writer.write( m )

    for key in writers:
        writers[ key ].close()

if __name__ == "__main__": __main__()
