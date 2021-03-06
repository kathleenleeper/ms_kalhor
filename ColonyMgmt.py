# imports
import pandas as pd
import numpy as np
import seaborn as sns
from datetime import datetime as dt
import logging as log
import re
import os
import glob
import gspread
# to do items
# add logging function; if colony is over 200, prioritize saccing and consolidating cages

## some fancy to dos:
## check that the csv is within an hour, i.e. up to date
## wrap helper functions more cleanly?
## eventually package as a script proper
## function to search the **NOTES** column; i.e. for mice that have bred with other mice etc

# #some fiddling to make sure we are not pulling from the wrong file
# file = "05227_mastersheet - Active.tsv"
# loc = os.getcwd() + "\\" + file
# os.path.getmtime(loc)

def checkTime(fn):
    time = os.path.getmtime(fn)
    ts = dt.utcfromtimestamp(time).strftime('%Y-%m-%d %H:%M:%S')
    return ts

def is_number(s):
    try:
        float(s)
        return s
    except ValueError:
        return float(''.join(ele for ele in s if ele.isdigit()))
        # return(s.extract('(\d+)', expand=False))


def importCleanDF(fn, sep = "\t",
                  skip = 0,
                  dropDeads = False,
                  dropTransfers = True,
                  dropHeaders = False,
                  convertDOB = True,
                  stats=True):

    df = pd.read_csv(fn, sep = sep,
                     skiprows = skip,
                     parse_dates = True,
                    dtype=str).dropna(axis = 0, how = 'all')
    print(f"Read in CSV: {fn}.\nFile was last modified at: {checkTime(fn)}\n") #logging

    df['TagClean'] = df.Tag.astype(str).apply(lambda x: is_number(x))

    df.Sex = df.Sex.fillna("temp")
    print("Animals without gender given temp. gender") #if animals are not gendered

    df.Cage = df.Cage.fillna('not included yet') #if animals are missing a cage
    print("Animals without cage given temp. cage") #if animals are not gendered

    df.Lineage = df.Lineage.fillna('NA') #if animals are missing a cage
    print("Animals without specified lineage given NA") #if animals are not gendered
    df = parsePlate(df)
    df = parseDOD(df, drop = dropDeads)
    if dropTransfers:
        df = dropTransferred(df)
    if dropHeaders:
        df = df[df.Cage.str.contains("NRB|HAT|HOP",
                                 case=False,
                                 na=False)].reset_index(drop=True) #drop the header rows & reset the index
        print("Retained rows with NRB, HAT, HOP, dropped otherwise drop headers")

    if convertDOB:
        df.DOB = cleanDOBs(df.DOB)

    if df.Ear.any():
        df.Ear =  df.Ear.apply(lambda row: "\'" + row if type(row)== str else np.nan) #convert ear tags to excel-clean formats
        print("Parsed ear tags for Excel formatting")
    if stats:
        colonyStats(df)
    return df

def cleanDOBs(s):
    '''uses .map() to apply changes'''
    dates = {date:pd.to_datetime(date, errors = 'coerce') for date in s.unique()}
    return s.map(dates)

def parseDOD(df, drop = True):
    df['DOD'] =  df.DOD.apply(lambda row: row.strip().lower() if type(row)== str else np.nan)
    df['parsedDOD'] = pd.to_datetime(df.DOD, errors = 'coerce')
    df['DOD'] = df['DOD'].fillna("-")
    if drop:
        init = colonyStats(df)
        df = df[(~df.parsedDOD.notnull()) & (~df.DOD.str.contains('sperm|Diss|f.d.|mia.',
                                   na = False))] #drop assorted dead mice
        print("initial counts:", init, "\nafter dropping dead", colonyStats(df))
    df = calcDisp(df)
    return df

def dropTransferred(df):
    init = colonyStats(df)
    df = df[~df.DOD.str.contains('transfer', na = False)]
    fin = colonyStats(df)
    print('after removing transferred', fin)
    return df

def collectAgeRange(df,
                    on_date,
                    oldest_requested_age,
                    youngest_requested_age,
                    lineage,
                    gender):
    early = pd.to_datetime(on_date) - pd.Timedelta(weeks = oldest_requested_age)
    late = pd.to_datetime(on_date) - pd.Timedelta(weeks = youngest_requested_age)
    mask = (df['DOB'] >= early)           & (df['DOB'] <= late)            & (df['Lineage'].str.contains(lineage))            & (df['Sex'].str.contains(gender))
    return early, late, mask

def colonyStats(df):
    '''helper function: returns number of mice, number of cages'''
    num_cages = len(df.Cage.unique())
    stats = {'numCages':len(df.Cage.unique()), 'numMice' : len(df)}
    if num_cages >=200:
        print("certainly cage reorg time")
    return stats

def makefn(string):
    '''returns string + formatted date to use as a file name'''
    return dt.today().strftime("%y%m%d-") + string + ".csv"

def tagSearch(string, df, column="Tag"):
    '''from a string, extracts all numbers and then searches for those numbers in a column'''
    find_t = re.findall(r'\d+', string)
    #search for that list in the spreadsheet and return only those rows
    return df[column].isin(find_t)
# def makeOutputs(df, upcase=True):
#     '''extremely specific to produce dispensible & sorted cage information'''
#     fineGrainedDispense = df.query("Dispensible >= 0.2").sort_values(["Dispensible", "Cage"], ascending=False)
#     cages = df.groupby("Cage").agg({'Dispensible':'first', #could be cleaner
#                                     'Cage':'size', #yay!
#                                     'Sex':'unique', #yay!
#                                     'Color':'unique',
#                                    'DOD':'unique'})   #yay!
#     return fineGrainedDispense, cages

def calcDisp(df):
    marks = df.groupby("Cage").DOD.value_counts(normalize=False,
                              dropna = False).unstack()
    filter_col = [col for col in marks if str(col).startswith('disp')]
    totalDisp = marks[filter_col].sum(axis=1).reset_index().rename({0: 'DispCount'},axis=1)
    df = df.merge(totalDisp)
    print('calculted total dispensible counts')

    df['CageSize'] = df.groupby("Cage")['Cage'].transform(len)
    print('calculated total cage sizes')

    df['DispPercent'] = df['DispCount']/df['CageSize']
    print('calculated % disp')

    return df


def parsePlate(df):
    plate = df['Plate'].str.split('-', n=1, expand = True) #split position from plate
    wells = plate[1].str.extract('([a-zA-Z]+)([^a-zA-Z]+)', expand=True) #split well into parts
    df['PlateID'] = plate[0]
    df['Row'] = wells[0]
    df['Column'] = wells[1]
    df['Position'] = df['Row']+ (df['Column'].apply(lambda x: str(x).lstrip("0")))
    return df

easyCats = ['Tag',
           'Cage',
           'Ear',
           'Sex',
           'Color','DOB',
           'Lineage',
             'Plate']


def consolidationFrames(df):
    allCages = df.groupby(['Cage']).agg({
        'DispPercent': 'mean',
        'DispCount': 'mean',
        'Cage': 'size',
        'Sex': 'unique',
        'DOD': 'unique',
        'Tag': 'unique',
        'Color': 'unique',
        'Ear': 'unique',
        'Lineage': 'unique',
        'DOB_clean': 'unique'
    }).sort_values('DispPercent', ascending=False)
    grp = df[(df.Sex == "F") & (df.DispPercent < 1) &
             (df.DispPercent > 0)].fillna("-")
    grp = grp.groupby(["Cage", 'DOD']).agg({
        'Cage': 'size',
        'CageSize': 'mean',
        'DispPercent': 'mean',
        'Tag': 'unique',
        'Color': 'unique',
        'Ear': 'unique',
        'Lineage': 'unique'
    })
    femaleSpecific = grp.rename({'Cage': 'Grp Size'}, axis=1).reset_index()
    return {'AllCages': allCages,'FemaleCons': femaleSpecific}

def makeConsolidations(df, save = True, popBack = False):
    '''wrapper to save both frames automatically to csv with appropriate filenames '''
    try:
        frames =  consolidationFrames(df)
        if save:
            for frame in frames:
                fn = makefn(frame)
                frames[frame].to_csv(fn, sep = "\t", index = True)
                print("Saved CSV with fns {}".format(fn))
        if popBack:
            print("returning {} frames".format(len(frames)))
            return frames
    except:
        print("error")

def getBreedingList(source_dir, date):
    '''func to parse a list of breeders in a given source file accoridng to Reza's standard output format for breeders. Provide a source directory and the date in the format "20XX-MM-DD"'''
    fns = glob.glob(f"{source_dir}/*{date}*/*")
    animal_frames = []

    for fn in fns:
        frame = pd.read_csv(fn, sep="\t")
        frame['Lineage'], frame['Date'] = fn[10:24].split("-", 1)
        frame['SourceFn'] = fn
        animal_frames.append(frame)

    animals = pd.concat(
        animal_frames,
        ignore_index=True)  #dont want pandas to try an align row indexes

    animals = animals.applymap(lambda x: x.strip("t") if isinstance(
        x, str) else x)  #remove t for easier comparison to big frame applys

    tagCols = ['Male', 'Female1',
               'Female2']  #grab columns with animals for flattening

    tag_frames = []
    for col in tagCols:
        frame = pd.concat((animals[i]
                           for i in [col, 'Lineage', 'Date', 'SourceFn']),
                          axis=1).rename({col: 'Tag'}, axis=1)
        tag_frames.append(frame)

    breeders = pd.concat(
        tag_frames,
        ignore_index=True)  #dont want pandas to try an align row indexes;
    return breeders



## speciality speed code for re-splitting genotypes by hgRNA tyep
def splitGenotypes(df):
    '''for splitting genotypes into hgRNA categories and summing to pick breeders when Reza hasn't, or for distribution, or whatever'''
    split = df['Genotype'].str.split(r'(\w,)', expand=True)
    split[6] = split[6].str.extract('(\d+)')
    split = split.rename({
        0: "E",
        2: 'I',
        4: "S",
        6: 'ina'
    }, axis=1).drop(columns=[1, 3, 5])

    newcols = []
    oldcols = []
    for col in split:
        colN = str(col) + "_num"
        split[colN] = pd.to_numeric(split[col], errors='coerce')
        oldcols.append(col)
        newcols.append(colN)

    split['summedhgRNAs'] = split[newcols].sum(axis=1)
    split['summedhgRNAs_active'] = split[newcols[0:3]].sum(axis=1)
    split = split.drop(oldcols[0:4], axis=1)
    df = df.merge(split, left_index=True, right_index=True)
    return df
