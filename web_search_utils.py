"""
Web Search Utilities
====================

Provides web search functionality for finding LinkedIn profiles and other information.
Adapted from the user's provided search code.
"""

import requests
from bs4 import BeautifulSoup
import re
import time
import random
from typing import List, Dict, Optional
import urllib.parse

def validate_linkedin_profile(linkedin_url: str, person_name: str = "") -> bool:
    """
    Validate LinkedIn profile to filter out invalid or sketchy profiles.
    
    Args:
        linkedin_url: The LinkedIn URL to validate
        person_name: Optional person name to cross-check
        
    Returns:
        True if profile appears valid, False otherwise
    """
    try:
        # Basic URL format validation
        if not linkedin_url or not isinstance(linkedin_url, str):
            return False
            
        # Must be a LinkedIn URL
        if 'linkedin.com/in/' not in linkedin_url.lower():
            return False
            
        # Extract profile slug
        profile_match = re.search(r'linkedin\.com/in/([^/?]+)', linkedin_url)
        if not profile_match:
            return False
            
        profile_slug = profile_match.group(1).lower()
        
        # Filter out suspicious patterns
        suspicious_patterns = [
            # Generic/bot-like patterns
            r'^user\d+$',
            r'^profile\d+$',
            r'^linkedin\d+$',
            r'^\d+$',  # Just numbers
            r'^[a-f0-9]{8,}$',  # Long hex strings
            
            # Obvious fake patterns
            r'test.*profile',
            r'fake.*user',
            r'bot.*\d+',
            r'spam.*\d+',
            
            # Too generic
            r'^a{3,}$',  # aaa, aaaa, etc.
            r'^.*-\d{6,}$',  # ending with long numbers
        ]
        
        for pattern in suspicious_patterns:
            if re.match(pattern, profile_slug):
                print(f"🚫 Filtered suspicious LinkedIn profile: {profile_slug}")
                return False
        
        # Check for reasonable length (LinkedIn slugs are typically 3-100 chars)
        if len(profile_slug) < 3 or len(profile_slug) > 100:
            return False
            
        # If person name provided, do basic name matching
        if person_name:
            # Clean person name for comparison
            clean_name = re.sub(r'[^a-zA-Z\s]', '', person_name.lower())
            name_parts = clean_name.split()
            
            # Profile slug should contain at least part of the name
            profile_lower = profile_slug.replace('-', ' ')
            
            # Check if any significant name part appears in profile
            if len(name_parts) > 0:
                name_found = False
                for part in name_parts:
                    if len(part) >= 3:  # Only check meaningful name parts
                        if part in profile_lower:
                            name_found = True
                            break
                
                # If no name parts found and name was provided, suspicious
                if not name_found and len(clean_name) > 0:
                    print(f"🚫 LinkedIn profile doesn't match name: {profile_slug} vs {person_name}")
                    return False
        
        # Basic HTTP check to see if profile exists (optional, with timeout)
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.head(linkedin_url, headers=headers, timeout=5, allow_redirects=True)
            
            # LinkedIn returns 999 for rate limiting, 404 for not found
            if response.status_code == 404:
                print(f"🚫 LinkedIn profile not found: {linkedin_url}")
                return False
            elif response.status_code == 403:
                # Forbidden might mean private profile, which is actually good
                pass
                
        except requests.RequestException:
            # Network issues shouldn't fail validation
            pass
        
        return True
        
    except Exception as e:
        print(f"Error validating LinkedIn profile {linkedin_url}: {e}")
        return False

def search_for_linkedin_profiles(person_name: str, company: str = "", max_results: int = 3) -> List[Dict]:
    """
    Search for LinkedIn profiles using web search.
    
    Args:
        person_name: Name of the person to search for
        company: Optional company name to refine search
        max_results: Maximum number of results to return
        
    Returns:
        List of dictionaries with profile information
    """
    try:
        # Construct search query
        if company:
            query = f"{person_name} {company} site:linkedin.com/in/"
        else:
            query = f"{person_name} site:linkedin.com/in/"
        
        # Encode query for URL
        encoded_query = urllib.parse.quote_plus(query)
        
        # Use DuckDuckGo as it's more privacy-friendly and less likely to block
        search_url = f"https://duckduckgo.com/html/?q={encoded_query}"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(search_url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        results = []
        
        # Find search result links
        result_links = soup.find_all('a', {'class': 'result__a'})
        
        for link in result_links[:max_results]:
            href = link.get('href')
            if href and 'linkedin.com/in/' in href:
                # Extract profile URL
                if href.startswith('/l/?kh=-1&uddg='):
                    # DuckDuckGo redirect link - extract actual URL
                    actual_url = urllib.parse.unquote(href.split('uddg=')[1]) if 'uddg=' in href else href
                else:
                    actual_url = href
                
                # Clean LinkedIn URL
                if 'linkedin.com/in/' in actual_url:
                    # Extract just the LinkedIn profile part
                    linkedin_match = re.search(r'linkedin\.com/in/([^/?]+)', actual_url)
                    if linkedin_match:
                        profile_slug = linkedin_match.group(1)
                        clean_url = f"https://www.linkedin.com/in/{profile_slug}"
                        
                        # Validate the profile before adding to results
                        if validate_linkedin_profile(clean_url, person_name):
                            # Try to extract name from the link text or URL
                            link_text = link.get_text(strip=True) if link else ""
                            
                            results.append({
                                'name': link_text or person_name,
                                'linkedin_url': clean_url,
                                'profile_slug': profile_slug
                            })
                        else:
                            print(f"🚫 Skipping invalid LinkedIn profile: {clean_url}")
        
        return results
        
    except Exception as e:
        print(f"Error searching for LinkedIn profiles: {e}")
        return []

def search_for_contact_info(person_name: str, company: str = "", title: str = "") -> Dict:
    """
    Search for contact information including LinkedIn profile.
    
    Args:
        person_name: Name of the person
        company: Company name
        title: Job title
        
    Returns:
        Dictionary with contact information
    """
    try:
        # Search for LinkedIn profile
        linkedin_results = search_for_linkedin_profiles(person_name, company, max_results=1)
        
        if linkedin_results:
            profile = linkedin_results[0]
            # Double-check validation before returning
            if validate_linkedin_profile(profile['linkedin_url'], person_name):
                return {
                    'name': person_name,
                    'title': title,
                    'company': company,
                    'linkedin': profile['linkedin_url'],
                    'found': True
                }
            else:
                print(f"🚫 Final validation failed for LinkedIn: {profile['linkedin_url']}")
        else:
            # If no LinkedIn found, return basic info
            return {
                'name': person_name,
                'title': title,
                'company': company,
                'linkedin': None,
                'found': False
            }
            
    except Exception as e:
        print(f"Error searching for contact info: {e}")
        return {
            'name': person_name,
            'title': title,
            'company': company,
            'linkedin': None,
            'found': False
        }

def extract_company_from_news(news_content: str) -> Optional[str]:
    """
    Extract company names from news content for better LinkedIn searches.
    
    Args:
        news_content: The news article content
        
    Returns:
        Company name if found, None otherwise
    """
    try:
        # Common patterns for company mentions
        company_patterns = [
            r'\b([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)\s+(?:Inc|Corp|LLC|Ltd|Limited|Company|Group|Holdings)\b',
            r'\b([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)\s+announced\b',
            r'\b([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)\s+said\b',
            r'\b([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)\s+CEO\b',
            r'\bCEO\s+of\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)\b'
        ]
        
        for pattern in company_patterns:
            matches = re.findall(pattern, news_content)
            if matches:
                # Return the first reasonable match
                for match in matches:
                    if len(match) > 2 and match not in ['The', 'This', 'That']:
                        return match
        
        return None
        
    except Exception as e:
        print(f"Error extracting company from news: {e}")
        return None

# Rate limiting to be respectful
_last_search_time = 0
_min_search_interval = 2  # seconds

def _rate_limit():
    """Simple rate limiting for web searches."""
    global _last_search_time
    current_time = time.time()
    time_since_last = current_time - _last_search_time
    
    if time_since_last < _min_search_interval:
        sleep_time = _min_search_interval - time_since_last
        time.sleep(sleep_time)
    
    _last_search_time = time.time() 