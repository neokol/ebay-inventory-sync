import csv
from datetime import datetime
import requests
import yaml
import os
from amazon_manager import AmazonInventoryManager
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
    target = config['settings'].get('target_platform').lower()
    if 'ebay' in target:
        manager = EbayManager(config)
    elif 'amazon' in target:
        manager = AmazonInventoryManager(config)
    else:
        logger.error(f"Invalid target platform specified: {target}. Must be 'ebay', 'amazon'")
        return
    
    items = []
    errored_items = []
    successful_items = []
    
    try:        
        items = manager.fetch_data()
        logger.info(f"Starting inventory update process at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} from: {config['settings']['mode']}")
        logger.info(f"Sync started for platform(s): {target.upper()}. {len(items)} items to process.")
        for item in items:
            batch = [item] 
            logger.info(f"Updating Item: {item['sku']}")
            success, sku = manager.update_inventory(batch, manager.session)

            if success:
                successful_items.append(sku)
            else:
                errored_items.append(sku)
                    
    finally:
        manager.close()
        logger.info("Process Complete. Summary:")
        logger.info(f"Total Successful: {len(successful_items)}")
        logger.info(f"Total Errored: {len(errored_items)}")
        
        if errored_items:
            clean_list = [str(i) for i in errored_items]
            logger.warning(f"List of Errored SKUs: {', '.join(clean_list)}")
        
if __name__ == "__main__":
    run_sync()