#!/usr/bin/env python
u"""
read_ATM2_icessn.py
Written by Tyler Sutterley (10/2017)

Reads Level-2 Airborne Topographic Mapper (ATM) Icessn Elevation, Slope, and
	Roughness data products provided by the National Snow and Ice Data Center
	http://nsidc.org/data/docs/daac/icebridge/ilatm2/index.html

Can be the following ATM icessn file types:
	BLATM2: Pre-Icebridge Airborne Topographic Mapper icessn product
	ILATM2: Airborne Topographic Mapper icessn product version 1
	ILATM2: Airborne Topographic Mapper icessn product  version 2 (*.csv)

INPUTS:
	full_filename: full path to ATM icessn file (can have tilde-prefix)

OUTPUTS:
Data variables for the given input icessn file format listed below:
	time: Time at which the aircraft passed the mid-point of the platelet
		Seconds since 2000-01-01 12:00:00 UTC
	latitude: Latitude of the center of the platelet (degrees)
	longitude: Longitude of the center of the platelet (degrees)
	elevation: Height of center of the platelet above WGS84 ellipsoid (meters)
	SNslope: South to North slope of the platelet (dimensionless)
	WEslope: West to East slope of the platelet (dimensionless)
	RMS: RMS fit of the ATM data to the plane. (meters)
	npt_used: Number of points used in estimating the plane parameters
	npt_edit: Number of points removed in estimating the plane parameters
	distance: Distance of the center of the block from the centerline of the
		aircraft trajectory (starboard = positive, port = negative). (meters)
	track: Track identifier (numbered 1...n, starboard to port, and 0 = nadir)

PYTHON DEPENDENCIES:
	numpy: Scientific Computing Tools For Python
		http://www.numpy.org
		http://www.scipy.org/NumPy_for_Matlab_Users

PROGRAM DEPENDENCIES:
	count_leap_seconds.py: determines the number of leap seconds for a GPS time

UPDATE HISTORY:
	Written 10/2017
"""
import os
import re
import numpy as np
from count_leap_seconds import count_leap_seconds

#-- PURPOSE: read the ATM Level-2 icessn data file
def read_ATM2_icessn(input_file, SUBSETTER=None):
	#-- regular expression pattern for extracting parameters
	regex_pattern = '(BLATM2|ILATM2)_(\d+)_(\d+)_smooth_nadir(.*?)(csv|seg|pt)$'
	rx = re.compile(regex_pattern, re.VERBOSE)
	#-- extract mission and other parameters from filename
	MISSION,YYMMDD,HHMMSS,AUX,SFX=rx.findall(os.path.basename(input_file)).pop()
	#-- early date strings omitted century and millenia (e.g. 93 for 1993)
	if (len(YYMMDD) == 6):
		ypre,month,day = np.array([YYMMDD[:2],YYMMDD[2:4],YYMMDD[4:]],dtype='i')
		year = (ypre + 1900.0) if (ypre >= 90) else (ypre + 2000.0)
	elif (len(YYMMDD) == 8):
		year,month,day = np.array([YYMMDD[:4],YYMMDD[4:6],YYMMDD[6:]],dtype='i')
	#-- input file column types for input variable
	file_dtype = {}
	file_dtype['names'] = ('seconds','latitude','longitude','elevation',
		'SNslope','WEslope','RMS','npt_used','npt_edit','distance','track')
	file_dtype['formats'] = ('f','f','f','f','f','f','f','u4','u4','f','u4')
	#-- convert RMS from centimeters to meters
	file_dtype['scale'] = (1.0,1.0,1.0,1.0,1.0,1.0,1.0/100.0,1,1,1.0,1)
	#-- compile regular expression operator for reading lines (extracts numbers)
	regex_pattern = '[-+]?(?:(?:\d*\.\d+)|(?:\d+\.?))(?:[Ee][+-]?\d+)?'
	regex = re.compile(regex_pattern, re.VERBOSE)
	#-- read the input file, split at lines and remove all commented lines
	with open(os.path.expanduser(input_file),'r') as f:
		file_contents=[i for i in f.read().splitlines() if re.match('^(?!#)',i)]
	#-- subset the data to indices if specified
	if SUBSETTER:
		file_contents = [file_contents[i] for i in SUBSETTER]
	#-- output python dictionary with variables
	ATM_L2_input = {}
	#-- create output variables with length equal to the number of file lines
	for key,val in zip(file_dtype['names'],file_dtype['formats']):
		ATM_L2_input[key] = np.zeros_like(file_contents, dtype=val)
	#-- for each line within the file
	for i,line_entries in enumerate(file_contents):
		#-- find numerical instances within the line
		line_contents = regex.findall(line_entries)
		#-- for each variable: save to dinput as float (integers will truncate)
		for j,k in enumerate(file_dtype['names']):
			ATM_L2_input[k][i]=np.float(line_contents[j])*file_dtype['scale'][j]
	#-- convert shot time (seconds of day) to J2000
	hour = np.floor(ATM_L2_input['seconds']/3600.0)
	minute = np.floor((ATM_L2_input['seconds'] % 3600)/60.0)
	second = ATM_L2_input['seconds'] % 60.0
	#-- First column in Pre-IceBridge and ICESSN Version 1 files is GPS time
	if (MISSION == 'BLATM2') or (SFX != 'csv'):
		#-- leap seconds for converting from GPS time to UTC
		S = calc_GPS_to_UTC(year,month,day,hour,minute,second)
	else:
		S = 0.0
	#-- calculation of Julian day
	JD = calc_julian_day(year,month,day,HOUR=hour,MINUTE=minute,SECOND=second+S)
	#-- converting to J2000 seconds
	ATM_L2_input['time'] = (JD - 2451545.0)*86400.0
	#-- return the input data
	return ATM_L2_input

#-- PURPOSE: calculate the Julian day from calendar date
#-- http://scienceworld.wolfram.com/astronomy/JulianDate.html
def calc_julian_day(YEAR, MONTH, DAY, HOUR=0, MINUTE=0, SECOND=0):
	JD = 367.*YEAR - np.floor(7.*(YEAR + np.floor((MONTH+9.)/12.))/4.) - \
		np.floor(3.*(np.floor((YEAR + (MONTH - 9.)/7.)/100.) + 1.)/4.) + \
		np.floor(275.*MONTH/9.) + DAY + 1721028.5 + HOUR/24. + MINUTE/1440. + \
		SECOND/86400.
	return np.array(JD,dtype=np.float)

#-- PURPOSE: calculate the number of leap seconds between GPS time (seconds
#-- since Jan 6, 1980 00:00:00) and UTC
def calc_GPS_to_UTC(YEAR, MONTH, DAY, HOUR, MINUTE, SECOND):
	GPS = 367.*YEAR - np.floor(7.*(YEAR + np.floor((MONTH+9.)/12.))/4.) - \
		np.floor(3.*(np.floor((YEAR + (MONTH - 9.)/7.)/100.) + 1.)/4.) + \
		np.floor(275.*MONTH/9.) + DAY - 723263.0
	GPS_Time = GPS*86400.0 + HOUR*1440.0 + MINUTE/60.0 + SECOND
	return count_leap_seconds(GPS_Time)