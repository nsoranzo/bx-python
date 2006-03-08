from __future__ import division

import math
import zlib

from fpconst import *
from Numeric import *
from RandomArray import *
from struct import *

MAGIC=0x4AB04612
VERSION=0

MAX=512*1024*1024 

class BinnedArray( object ):
    def __init__( self, bin_size=512*1024, default=NaN, max_size=MAX ):
        self.max_size = max_size
        self.bin_size = bin_size
        self.nbins = int( math.ceil( ( max_size / self.bin_size ) ) )
        self.bins = [ None ] * self.nbins
        self.default = default
    def get_bin_offset( self, index ):
        return index // self.bin_size, index % self.bin_size
    def init_bin( self, index ):
        # self.bins[index] = zeros( self.bin_size ) * self.default
        self.bins[index] = resize( array(self.default, typecode="f"), (self.bin_size,) )
    def get( self, key ):
        bin, offset = self.get_bin_offset( key )
        if self.bins[bin]:
            return self.bins[bin][offset]
        else:
            return self.default
    def set( self, key, value ):
        bin, offset = self.get_bin_offset( key )
        if not self.bins[bin]: self.init_bin( bin )
        self.bins[bin][offset] = value
    def get_range( self, start, end ):
        size = end - start
        assert size >= 0
        rval = []
        while size > 0:
            bin, offset = self.get_bin_offset( start )
            delta = self.bin_size - offset
            if self.bins[bin] is None:
                if delta < size:
                    rval.append( resize( array(self.default, typecode="f"), (delta,) ) )
                    size -= delta
                    start += delta
                else:
                    rval.append( resize( array(self.default, typecode="f"), (size,) ) )
                    size = 0
            else:
                if delta < size:
                    rval.append( self.bins[bin][offset:offset+delta] )
                    size -= delta
                    start += delta
                else:
                    rval.append( self.bins[bin][offset:offset+size] )
                    size = 0
        return concatenate( rval )
    def __getitem__( self, key ):
        if isinstance( key, slice ):
            start, stop, stride = key.indices( self.max_size )
            assert stride == 1, "Slices with strides are not supported"
            return self.get_range( start, stop )
        else:
            return self.get( key )
    def __setitem__( self, key, value ):
        return self.set( key, value )
    def to_file( self, f ):
        # Write header
        write_packed( f, ">5I", MAGIC, VERSION, self.max_size, self.bin_size, self.nbins )
        # Struct module can't deal with NaN and endian conversion, we'll hack around that with Numeric
        a = array( self.default, typecode="f" ) 
        if LittleEndian: a = a.byteswapped()
        f.write( a.tostring() )
        # Save current position (start of bin offsets)
        index_start_pos = f.tell()
        # Skip forward to save space for index
        f.seek( calcsize( ">2I" ) * self.nbins, 1 )
        bin_pos_and_size = []
        # Write each bin
        for bin in self.bins:
            if bin is None: 
                bin_pos_and_size.append( ( 0, 0 ) )
            else:
                assert bin.typecode() == 'f'
                if LittleEndian:
                    s = bin.byteswapped().tostring()
                else:
                    s = bin.tostring()
                compressed = zlib.compress( s )
                bin_pos_and_size.append( ( f.tell(), len( compressed ) ) )
                f.write( compressed )
        # Go back and fill in table
        f.seek( index_start_pos )
        for pos, size in bin_pos_and_size:
            write_packed( f, ">2I", pos, size )
            
class FileBinnedArray( object ):
    def __init__( self, f):
        self.f = f
        M, V, max_size, bin_size, nbins = read_packed( f, ">5I" )
        assert M == MAGIC
        assert V == VERSION 
        self.max_size = max_size
        self.bin_size = bin_size
        self.nbins = nbins        
        self.bins = [ None ] * self.nbins
        # Hacking again
        s = f.read( 4 )
        a = fromstring( s, "f" )
        if LittleEndian: a = a.byteswapped()
        self.default = a[0]
        # Read bin sizes and offsets
        self.bin_pos = []
        self.bin_sizes = []
        for i in range( nbins ):
            pos, size = read_packed( f, ">2I" )
            self.bin_pos.append( pos )
            self.bin_sizes.append( size )
    def get_bin_offset( self, index ):
        return int( index // self.bin_size ), int( index % self.bin_size )
    def load_bin( self, index ):
        assert self.bin_pos[index] != 0
        self.f.seek( self.bin_pos[index] )
        raw = self.f.read( self.bin_sizes[index] )
        a = fromstring( zlib.decompress( raw ), "f" )
        if LittleEndian:
            a = a.byteswapped()
        assert len( a ) == self.bin_size
        self.bins[index] = a
    def get( self, key ):
        bin, offset = self.get_bin_offset( key )
        if self.bins[bin]:
            return self.bins[bin][offset]
        elif self.bin_pos[bin]:
            self.load_bin( bin )
            return self.bins[bin][offset]
        else:
            return self.default
    def get_range( self, start, end ):
        size = end - start
        assert size >= 0
        rval = []
        while size > 0:
            bin, offset = self.get_bin_offset( start )
            delta = self.bin_size - offset
            if self.bins[bin] is None and self.bin_pos[bin] != 0:
                self.load_bin( bin )
            if self.bins[bin] is None:
                if delta < size:
                    rval.append( resize( array(self.default, typecode="f"), (delta,) ) )
                    size -= delta
                    start += delta
                else:
                    rval.append( resize( array(self.default, typecode="f"), (size,) ) )
                    size = 0
            else:
                if delta < size:
                    rval.append( self.bins[bin][offset:offset+delta] )
                    size -= delta
                    start += delta
                else:
                    rval.append( self.bins[bin][offset:offset+size] )
                    size = 0
        return concatenate( rval )
    def __getitem__( self, key ):
        if isinstance( key, slice ):
            start, stop, stride = key.indices( self.max_size )
            assert stride == 1, "Slices with strides are not supported"
            return self.get_range( start, stop )
        else:
            return self.get( key )      
    
def write_packed( f, pattern, *vals ):
    f.write( pack( pattern, *vals ) )
    
def read_packed( f, pattern ):
    rval = unpack( pattern, f.read( calcsize( pattern ) ) )
    if len( rval ) == 1: return rval[0]
    return rval
    
if __name__ == "__main__":
    source = []
    for i in range( 13 ):
        if random() < 0.5:
            source = concatenate( ( source, random_integers( 10, 0, 9456 ) ) )
        else:
            source = concatenate( ( source, zeros( 8972 ) ) )
    # Set on target
    target = BinnedArray( 128, NaN, len( source ) )
    for i in range( len( source ) ):
        if not isNaN( source[i] ):
            target[i] = source[i]
    # Verify
    for i in range( len( source ) ):
        assert source[i] == target[i], "No match, index: %d, source: %d, target: %d" % ( i, source[i], target[i] )
    # Verfiy with slices
    for i in range( 10 ):
        a = int( random() * len( source ) )
        b = int( random() * len( source ) )
        if b < a: a, b = b, a
        assert source[a:b] == target[a:b], "No match, index: %d:%d, source: %s, target: %s" % \
            ( a, b, ",".join( map( str, source[a:a+10] ) ), ",".join( map( str, target[a:a+10] ) ) )
    # With a file
    target.to_file( open( "/tmp/foo", "w" ) )
    target2 = FileBinnedArray( open( "/tmp/foo" ) )
    # Verify
    for i in range( len( source ) ):
        assert source[i] == target2[i], "No match, index: %d, source: %d, target: %d" % ( i, source[i], target2[i] )
    # Verfiy with slices
    target2 = FileBinnedArray( open( "/tmp/foo" ) )
    for i in range( 10 ):
        a = int( random() * len( source ) )
        b = int( random() * len( source ) )
        if b < a: a, b = b, a
        assert source[a:b] == target[a:b], "No match, index: %d:%d, source: %s, target: %s" % \
            ( a, b, ",".join( map( str, source[a:a+10] ) ), ",".join( map( str, target2[a:a+10] ) ) )
            
            
            