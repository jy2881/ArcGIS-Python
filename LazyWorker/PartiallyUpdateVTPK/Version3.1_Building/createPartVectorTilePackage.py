# -*- coding: utf-8 -*-
__author__ = 'mu_xiaoyan'
# !/usr/bin/python
# Version 3.1

# What's New in Version 3.1 ?
# Create part vtpk at bundle level rather than tile level.

# What's New in version 3.0 ?
# Automatically get the aux files from the original advanced vtpk. then generate the delta new part vtpk.

import arcpy
import os
import shutil
import time
import zipfile
import sys

# uncompress the .zip file to folder
def unzip(newPartZipPath):
    try:
        file_zip = zipfile.ZipFile(newPartZipPath, 'r')
        for file in file_zip.namelist():
            # print "unziping..."
            extractFolder = os.path.splitext(newPartZipPath)[0]
            file_zip.extract(file, extractFolder)
        file_zip.close()
        os.remove(newPartZipPath)
        print("unzip succeed!")
        return extractFolder
    except:
        print("unzip failed, please provde a validates path")
        return ""

# Analyzing Original vtpk file to get the tiling scheme and index polygon and also get the service type
def analysis_original_vtpk(origin_vtpk_path):

    origin_workspace = os.path.dirname(origin_vtpk_path)
    origin_vtpk_name = os.path.basename(origin_vtpk_path)
    # Create temp workspace
    timeStamp = time.strftime('%Y%m%d%H%M%S', time.localtime(time.time()))
    temp_workspace = os.path.join(origin_workspace, str(timeStamp))
    os.mkdir(temp_workspace)
    try:
        # copy original vtpk
        bak_original_vtpk = shutil.copy(origin_vtpk_path, temp_workspace)
        unzip(bak_original_vtpk)
        # Locate vtpk aux files
        tile_scheme_name = "customizedScheme.xml"
        index_polygon_name = "originMasterIndex.shp"
        vtpk_extract_dir = origin_vtpk_name.split(".")[0]
        arcpy.AddMessage(vtpk_extract_dir)
        aux_files_path = temp_workspace+ r"\\"+ vtpk_extract_dir+ r"\AdvVtpkAuxFiles"
        index_polygon = os.path.join(aux_files_path, index_polygon_name)
        tile_scheme = os.path.join(aux_files_path, tile_scheme_name)
        # get the service type
        if os.path.exists(tile_scheme):
            service_type = "EXISTING"
        else:
            tile_scheme = ""
            service_type = "ONLINE"
        aux_paras = [index_polygon, tile_scheme, service_type,temp_workspace]
        return aux_paras
    except:
        arcpy.AddMessage("Original vtpk does not exist.")

# Calculate bundle extent
def calculate_bundle_extent(workspace,AOI,index_polygon):
    arcpy.CreateFileGDB_management(workspace,"tempGDB.gdb")
    arcpy.env.workspace = os.path.join(workspace,"tempGDB.gdb")
    arcpy.AddMessage("Current workspace: {0}".format(arcpy.env.workspace))
    AOI_lyr = arcpy.MakeFeatureLayer_management(AOI, "AOI_lyr")
    IndexPolygon_lyr = arcpy.MakeFeatureLayer_management(index_polygon, "IndexPolygon_lyr")

    # Select and write all index tiles by location -- IndexPolygon_lyr intersect AOI_lyr
    locRes = arcpy.SelectLayerByLocation_management(IndexPolygon_lyr, 'intersect', AOI_lyr)
    locRes_lyr = arcpy.MakeFeatureLayer_management(arcpy.CopyFeatures_management(locRes,"locRes"),"locRes_lyr")
    arcpy.AddMessage(locRes_lyr)
    # Select and write most detailed index tiles in AOI -- LOD=max and Leaf=true
    maxLOD_locRes = arcpy.SelectLayerByAttribute_management(locRes_lyr, 'SUBSET_SELECTION', '("LOD" = (SELECT MAX("LOD") from locRes)) AND ("LEAF" = 1)')
    arcpy.AddMessage(maxLOD_locRes)
    maxLOD_locRes_lyr = arcpy.MakeFeatureLayer_management(arcpy.CopyFeatures_management(maxLOD_locRes, "maxLOD_locRes"), "maxLOD_locRes_lyr")
    arcpy.AddMessage("maxLOD_locRes Copy Done!")

    # Select -6 level tiles
    bundleExt = arcpy.SelectLayerByAttribute_management(locRes_lyr, 'NEW_SELECTION', '"LOD" = ((SELECT MAX("LOD") FROM locRes)-6)')
    bundleExt_lyr = arcpy.MakeFeatureLayer_management(arcpy.CopyFeatures_management(bundleExt, 'bundleExt'))
    arcpy.AddMessage("bundleExt Copy Done!")
    # Bundle Extent
    bundleExt_AOI = arcpy.SelectLayerByLocation_management(bundleExt_lyr ,'intersect', maxLOD_locRes_lyr)
    bundleExt_AOI_lyr = arcpy.MakeFeatureLayer_management(arcpy.CopyFeatures_management(bundleExt_AOI, 'polygonIndexPart'))

    # Select all Indexed Polygon
    arcpy.SelectLayerByAttribute_management(IndexPolygon_lyr,'CLEAR_SELECTION' )
    IndexPolygonPartLoc =  arcpy.SelectLayerByLocation_management(IndexPolygon_lyr ,'intersect', bundleExt_AOI_lyr)
    IndexPolygonPart = arcpy.MakeFeatureLayer_management(arcpy.CopyFeatures_management(IndexPolygonPartLoc, 'bundleExt'))


    return IndexPolygonPart

# Create Partial VTPK with new part index
def create_partial_vtpk(workspace, IndexPolygonPart, in_map, out_part_vtpk, service_type, tile_scheme):
    arcpy.AddMessage("Service Type: " + service_type)
    try:
        arcpy.CreateVectorTilePackage_management(in_map=in_map,
                                                 output_file=out_part_vtpk,
                                                 service_type=service_type,
                                                 tiling_scheme=tile_scheme,
                                                 tile_structure="INDEXED",
                                                 index_polygons=IndexPolygonPart)
    except Exception as err:
        arcpy.AddError(err)
        print(err)
    # arcpy.Delete_management(IndexPolygonPart)
    return True


def main(argv=None):
    # Input map in the current project
    in_map = arcpy.GetParameterAsText(0)
    arcpy.AddMessage("Input map : {0}.".format(in_map))

    # Specify the area where the delta new part vtpk need to be created
    AOI = arcpy.GetParameterAsText(1)
    arcpy.AddMessage("AOI : {0}.".format(AOI))

    # Choose the existing original adv vtpk
    origin_vtpk = arcpy.GetParameterAsText(2)
    arcpy.AddMessage("Original vtpk : {0}.".format(origin_vtpk))

    # Specify name and workspace for new part vtpk
    out_part_vtpk = arcpy.GetParameterAsText(3)
    arcpy.AddMessage("New part vtpk : {0}.".format(out_part_vtpk))

    execute(in_map, AOI, origin_vtpk, out_part_vtpk)

def execute(in_map, AOI, origin_vtpk_path, out_part_vtpk):
    workspace = os.path.dirname(out_part_vtpk)
    aux_paras = analysis_original_vtpk(origin_vtpk_path)
    index_polygon = aux_paras[0]
    tile_scheme = aux_paras[1]
    service_type = aux_paras[2]
    temp_workspace = aux_paras[3]
    arcpy.AddMessage(index_polygon + "/n"+tile_scheme+"/n"+service_type)
    IndexPolygonPart = calculate_bundle_extent(workspace,AOI,index_polygon)
    # Excute create_partial_vtpk function
    create_partial_vtpk(workspace, IndexPolygonPart, in_map, out_part_vtpk, service_type, tile_scheme)
    # if os.path.exists(out_part_vtpk):
    #     shutil.rmtree(temp_workspace)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
