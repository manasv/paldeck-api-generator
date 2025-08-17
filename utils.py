def find_pal_image_url(soup):
    """Find the best image URL for a Pal from the soup object."""
    # Try icon tab first
    icon_tab = soup.find("div", id="pi-tab-2")
    if icon_tab:
        img = icon_tab.find("img", class_="pi-image-thumbnail")
        if img and img.get("src"):
            return img["src"]
    # Fallback: first infobox image
    img = soup.find("img", class_="pi-image-thumbnail")
    if img and img.get("src"):
        return img["src"]
    return None
def smart_capitalize(word):
    if word.startswith("(") and word.endswith(")") and len(word) > 2:
        # e.g. (Special)
        return "(" + word[1:-1].capitalize() + ")"
    elif word.startswith("("):
        return "(" + word[1:].capitalize()
    elif word.endswith(")"):
        return word[:-1].capitalize() + ")"
    else:
        return word.capitalize()
