import csv
from datetime import datetime
import requests
import yaml
import os
from loguru import logger # type: ignore

from ebay_manager import EbayManager
# --- CONFIGURATION ---
def load_config():
    try:
        with open("config.yaml", "r") as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"Critical error loading config.yaml: {e}")
        exit(1)

def run_sync():
    config = load_config()
    ebay_manager = EbayManager(config)
    items = []
    errored_items = []
    successful_items = []
    
    try:
        
        items = ebay_manager.fetch_data()
        logger.info(f"Starting inventory update process at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} from: {config['settings']['mode']}")
        logger.info(f"Loaded {len(items)} items. Starting updates...")
            
        for item in items:
            batch = [item] 
            logger.info(f"Updating Item: {item['sku']}")
                
            success, sku = ebay_manager.update_inventory(batch, ebay_manager.session)
            if success:
                successful_items.append(sku)
            else:
                errored_items.append(sku)
                    
    finally:
        ebay_manager.close()
        logger.info("Process Complete. Summary:")
        logger.info(f"Total Successful: {len(successful_items)}")
        logger.info(f"Total Errored: {len(errored_items)}")
        
        if errored_items:
            clean_list = [str(i) for i in errored_items]
            logger.warning(f"List of Errored SKUs: {', '.join(clean_list)}")
        
if __name__ == "__main__":
    run_sync()