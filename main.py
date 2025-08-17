from scraper import scrape_pals, scrape_pal_details
from storage import save_to_json, save_individual_pal
from scraper import download_pal_image

def main():
    try:
        # Scrape base data
        pal_data = scrape_pals()
        print(f"Scraped {len(pal_data)} base Pal records")
        
        # Save combined pals.json
        save_to_json(pal_data)
        print("Saved combined data to pals.json")
        
        # Process individual Pals
        for idx, pal in enumerate(pal_data, 1):
            print(f"Processing {pal.name} ({idx}/{len(pal_data)})")
            # Get detailed info
            details = scrape_pal_details(pal.name)
            # Download image
            download_pal_image(pal.name, pal.id)
        
            # Create complete dataset
            full_data = {
                **pal.to_dict(),  # Base fields
                **details         # Additional fields
            }
            # Save individual file
            save_individual_pal(full_data)
        print("All individual Pal files and images saved.")
        
    except Exception as e:
        print(f"Error occurred: {str(e)}")

if __name__ == "__main__":
    main() 

