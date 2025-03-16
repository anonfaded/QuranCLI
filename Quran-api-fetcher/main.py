import requests
from colorama import Fore, Style, init

init(autoreset=True)

BASE_URL = "https://quranapi.pages.dev/api/"

def fetch_verses(surah, start_ayah, end_ayah):
    try:
        # Fetch the whole surah
        url = f"{BASE_URL}{surah}.json"
        response = requests.get(url, timeout=10)
        
        if response.status_code != 200:
            print(Fore.RED + f"Error: HTTP {response.status_code}")
            return None

        data = response.json()
        
        if not data:
            print(Fore.RED + "Invalid response structure")
            return None
            
        # Extract verses from the surah
        ayahs = []
        for i, ayah in enumerate(data['english'], start=1):
            if start_ayah <= i <= end_ayah:
                ayahs.append({
                    "number": i,
                    "text": ayah,
                    "arabic1": data['arabic1'][i-1],
                    "arabic2": data['arabic2'][i-1],
                })
        
        return ayahs or None

    except Exception as e:
        print(Fore.RED + f"Request failed: {str(e)}")
        return None

def display_ayahs(ayahs):
    print(Fore.CYAN + "\n📜 Quranic Verses Retrieved:\n" + "-" * 50)

    for ayah in ayahs:
        print(Fore.GREEN + f"[{ayah['number']}] " + Fore.WHITE + ayah["text"])
        print(Fore.YELLOW + f"Arabic: {ayah['arabic1']}")
        print("-" * 20)
    
    print("-" * 50)

def main():
    print(Fore.MAGENTA + "Quran API Verse Fetcher\n" + "=" * 30)

    try:
        surah = int(input(Fore.BLUE + "Enter Surah number (1-114): " + Fore.WHITE))
        start_ayah = int(input(Fore.BLUE + "Enter start Ayah number: " + Fore.WHITE))
        end_ayah = int(input(Fore.BLUE + "Enter end Ayah number: " + Fore.WHITE))

        if surah < 1 or surah > 114:
            print(Fore.RED + "Invalid Surah number. Must be between 1 and 114.")
            return
        
        if start_ayah > end_ayah or start_ayah < 1:
            print(Fore.RED + "Invalid Ayah range.")
            return

        print(Fore.YELLOW + "\nFetching verses... Please wait.\n")
        
        ayahs = fetch_verses(surah, start_ayah, end_ayah)

        if ayahs:
            display_ayahs(ayahs)
        else:
            print(Fore.RED + "Failed to fetch verses.")

    except ValueError:
        print(Fore.RED + "Invalid input! Please enter numbers only.")

if __name__ == "__main__":
    main()
