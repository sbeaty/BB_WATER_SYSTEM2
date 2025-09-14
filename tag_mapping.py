"""
Tag name mapping between threshold CSV names and actual historian database tag names.
"""

# Mapping from CSV tag names to actual database tag names with descriptions and lines
TAG_MAPPING = {
    # PC Line (Potato Processing)
    'FT5101_TotalLts': {
        'db_tag': 'WRP26_FT5101_Total',
        'description': 'PC Barrel Washer',
        'line': 'PC Line'
    },
    'FT5201_TotalLts': {
        'db_tag': 'WRP26_FT5201_Total', 
        'description': 'Peelers',
        'line': 'PC Line'
    },
    'FT5301_TotalLts': {
        'db_tag': 'WRP26_FT5301_Total',
        'description': 'Slicers',
        'line': 'PC Line'
    },
    'FT5402_TotalLts': {
        'db_tag': 'WRP26_FT5402_Total',
        'description': 'Speed-Wash & ROCD',
        'line': 'PC Line'
    },
    'FT5240_Total_m3': {
        'db_tag': 'WRP26_FT5240_Total_m3',
        'description': 'TOMRA',
        'line': 'PC Line'
    },
    'FT5241_Total_m3': {
        'db_tag': 'WRP26_FT5241_Total_m3',
        'description': 'TOMRA/Sormac/Auto Halver Hot Water',
        'line': 'PC Line'
    },
    'FT5242_Total_m3': {
        'db_tag': 'WRP26_FT5242_Total_m3',
        'description': 'DAF Cold Water',
        'line': 'PC Line'
    },
    
    # CK Line (Carrot Processing)
    'FT3101_Totalizer1': {
        'db_tag': 'WRCKNEW_FT3101_Totalizer1',
        'description': 'CK Peeler Fresh Water',
        'line': 'CK Line'
    },
    'FT3104_Totalizer1': {
        'db_tag': 'WRCKNEW_FT3104_Totalizer1',
        'description': 'CK Peeler Water',
        'line': 'CK Line'
    },
    'FT3106_Totalizer1': {
        'db_tag': 'WRCKNEW_FT3106_Totalizer1',
        'description': 'CK Peeler Water',
        'line': 'CK Line'
    },
    'FT3105_Totalizer1': {
        'db_tag': 'WRCKNEW_FT3105_Totalizer1',
        'description': 'CK Peeler Water',
        'line': 'CK Line'
    },
    'FT3503_l1_Process_variables_Totalizer1': {
        'db_tag': 'WRCKNEW_FT3503_Usage.NonErasable',
        'description': 'CK Slicers / Slide / ROCD / Hoses',
        'line': 'CK Line'
    },
    'HotWater_Total_lit': {
        'db_tag': 'WRCKNEW_HotWaterRMF_Value',
        'description': 'CK Hot Water',
        'line': 'CK Line'
    },
    'CK_Line1_HotWater_NettTotal': {
        'db_tag': 'CK_Line1_HotWater_NettTotal',
        'description': 'CK Hot Water',
        'line': 'CK Line'
    },
    
    # TC Line (Tomato Processing)  
    'FT2104_Usage_NonErasable': {
        'db_tag': 'WRTC_FT2104_Total',
        'description': 'TC Water Usage',
        'line': 'TC Line'
    },
    'FT2201_Usage_NonErasable': {
        'db_tag': 'WRTC_FT2201_Total',
        'description': 'TC Water Usage',
        'line': 'TC Line'
    },
    'FT2301_Usage2_NonErasable': {
        'db_tag': 'WRTC_FT2301_Total',
        'description': 'TC Water Usage',
        'line': 'TC Line'
    },
    'FT2102_Usage_NonErasable': {
        'db_tag': 'WRTC_FT2102_Total',
        'description': 'TC Water Usage',
        'line': 'TC Line'
    },
    'FT2302_Usage2_NonErasable': {
        'db_tag': 'WRTC_FT2302_Total',
        'description': 'TC Water Usage',
        'line': 'TC Line'
    },
    
    # EP Line (Eggplant Processing)
    'FM8201Total_Actual': {
        'db_tag': 'WREP_FM8201Total',
        'description': 'EP Water Usage',
        'line': 'EP Line'
    },
    
    # Utilities & Other
    'BoilerHL_9_4': {
        'db_tag': 'BoilerHL_9_4',
        'description': 'Boiler Hot Loop',
        'line': 'Utilities'
    },
    'PLC_Interface_WetScrub_Season_Status_2_': {
        'db_tag': 'PLC_Interface_WetScrub_Season_Status_2_',
        'description': 'Wet Scrub Season Status',
        'line': 'Utilities'
    },
    'TEST_HIGH': {
        'db_tag': 'TEST_HIGH',
        'description': 'Test Tag High',
        'line': 'Test'
    },
    'TEST_FIXED': {
        'db_tag': 'TEST_FIXED',
        'description': 'Test Tag Fixed',
        'line': 'Test'
    },
}

def get_database_tag_name(csv_tag_name):
    """
    Convert CSV tag name to actual database tag name.
    
    Args:
        csv_tag_name (str): Tag name from CSV/threshold configuration
        
    Returns:
        str: Actual database tag name
    """
    mapping = TAG_MAPPING.get(csv_tag_name, csv_tag_name)
    if isinstance(mapping, dict):
        return mapping['db_tag']
    return mapping

def get_tag_info(csv_tag_name):
    """
    Get complete tag information including description and line.
    
    Args:
        csv_tag_name (str): Tag name from CSV/threshold configuration
        
    Returns:
        dict: Tag information with db_tag, description, and line
    """
    mapping = TAG_MAPPING.get(csv_tag_name, {
        'db_tag': csv_tag_name,
        'description': csv_tag_name,
        'line': 'Unknown'
    })
    if isinstance(mapping, dict):
        return mapping
    return {
        'db_tag': mapping,
        'description': csv_tag_name,
        'line': 'Unknown'
    }

def get_csv_tag_name(database_tag_name):
    """
    Convert database tag name back to CSV tag name.
    
    Args:
        database_tag_name (str): Actual database tag name
        
    Returns:
        str: CSV tag name
    """
    # Create reverse mapping
    reverse_mapping = {v: k for k, v in TAG_MAPPING.items()}
    return reverse_mapping.get(database_tag_name, database_tag_name)

def list_all_mappings():
    """List all tag mappings for debugging."""
    print("Tag Mappings (CSV -> Database):")
    print("-" * 50)
    for csv_name, db_name in TAG_MAPPING.items():
        print(f"{csv_name:40} -> {db_name}")