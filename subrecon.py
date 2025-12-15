#!/usr/bin/env python3
"""
subrecon.py - כלי מתקדם לאיתור סאב-דומיינים ללא API
משולב פסיבי ואקטיבי עם מקורות רבים ושיטות מתקדמות
"""

import argparse
import requests
import json
import time
import sys
import os
import re
import random
import socket
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse, urljoin
from collections import OrderedDict
from bs4 import BeautifulSoup

# התקנת התלויות הנדרשות:
# pip install requests beautifulsoup4 dnspython

try:
    import dns.resolver
    import dns.query
    DNS_AVAILABLE = True
except ImportError:
    DNS_AVAILABLE = False
    print("[!] Warning: dnspython not installed. Some features will be limited.")
    print("[!] Install with: pip install dnspython")

try:
    from colorama import init, Fore, Style
    init(autoreset=True)
    COLORS = True
except ImportError:
    COLORS = False
    Fore = Style = type('obj', (object,), {'__getattr__': lambda *args: ''})()

try:
    from tqdm import tqdm
    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False

class SubdomainEnumerator:
    def __init__(self, domain, output_file=None, threads=20, timeout=30):
        self.domain = domain
        self.output_file = output_file
        self.threads = threads
        self.timeout = timeout
        self.subdomains = set()
        self.validated_subs = set()
        
        # User Agents שונים - תיקון: הוספתי את זה לפני קריאה ל-_create_session
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15',
        ]
        
        self.session = self._create_session()
        
        # רשימת name servers ציבוריים
        self.nameservers = [
            '8.8.8.8',      # Google
            '8.8.4.4',      # Google
            '1.1.1.1',      # Cloudflare
            '1.0.0.1',      # Cloudflare
            '9.9.9.9',      # Quad9
            '208.67.222.222', # OpenDNS
            '208.67.220.220', # OpenDNS
        ]
        
        # wordlist בסיסית
        self.common_subdomains = self._load_common_subdomains()
    
    def _create_session(self):
        """יצירת session עם headers מתאימים"""
        session = requests.Session()
        session.headers.update({
            'User-Agent': random.choice(self.user_agents),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        session.verify = False
        # השתמשתי ב-try/except במקום disable_warnings ישיר
        try:
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        except:
            pass
        return session
    
    def _load_common_subdomains(self):
        """טעינת רשימת סאב-דומיינים נפוצים"""
        common = [
            # בסיסיים
            'www', 'mail', 'ftp', 'smtp', 'pop', 'pop3', 'imap', 'webmail',
            # אדמיניסטרציה
            'admin', 'administrator', 'login', 'dashboard', 'control', 'cpanel',
            'whm', 'plesk', 'webadmin', 'server', 'ns1', 'ns2', 'ns3', 'ns4',
            # פיתוח
            'dev', 'development', 'test', 'testing', 'stage', 'staging', 'beta',
            'alpha', 'demo', 'sandbox', 'lab', 'experiment',
            # אפליקציות
            'app', 'api', 'api2', 'api3', 'mobile', 'm', 'wap', 'apps',
            # שירותים
            'blog', 'news', 'forum', 'forums', 'support', 'help', 'kb',
            'wiki', 'docs', 'documentation', 'status', 'monitor', 'stats',
            'analytics', 'metrics', 'graph', 'grafana', 'prometheus',
            # קבצים ואחסון
            'files', 'file', 'upload', 'download', 'storage', 'backup',
            'share', 'shared', 'public', 'private', 'secure', 's',
            # שירותי ענן
            'aws', 'azure', 'cloud', 'gcp', 's3', 'bucket', 'blob', 'cdn',
            'cloudfront', 'akamai', 'fastly', 'storage',
            # שירותים פנימיים
            'internal', 'intranet', 'vpn', 'proxy', 'gateway', 'router',
            'firewall', 'fw', 'switch', 'hub', 'printer', 'print',
            # CI/CD
            'jenkins', 'git', 'gitlab', 'github', 'bitbucket', 'svn',
            'docker', 'registry', 'nexus', 'artifactory', 'sonar',
            # בסיסי נתונים
            'db', 'database', 'mysql', 'postgres', 'mongo', 'redis',
            'elasticsearch', 'kibana', 'logstash', 'rabbitmq',
            # אימייל
            'mail', 'smtp', 'pop3', 'imap', 'exchange', 'owa', 'webmail',
            # DNS
            'dns', 'bind', 'ns', 'nameserver', 'resolver',
            # אחרים
            'portal', 'hub', 'center', 'core', 'main', 'primary',
            'secondary', 'backup', 'failover', 'replica', 'cluster',
            'node', 'service', 'services', 'svc', 'endpoint',
            'gateway', 'router', 'switch', 'firewall', 'fw',
            'bastion', 'jump', 'jumpserver', 'terminal',
            'vcenter', 'esxi', 'hyperv', 'xen', 'kvm',
            'sharepoint', 'jira', 'confluence', 'bitbucket',
            'teamcity', 'bamboo', 'octopus', 'ansible',
            'puppet', 'chef', 'salt', 'terraform',
            'kafka', 'zookeeper', 'spark', 'hadoop',
            'hive', 'hbase', 'cassandra', 'couchbase',
            'orientdb', 'neo4j', 'arangodb', 'influxdb',
            'prometheus', 'alertmanager', 'thanos',
            'consul', 'etcd', 'zookeeper', 'eureka',
            'istio', 'linkerd', 'envoy', 'traefik',
            'nginx', 'apache', 'tomcat', 'jetty',
            'iis', 'weblogic', 'websphere', 'jboss',
            'wildfly', 'glassfish', 'payara',
            'php', 'python', 'ruby', 'node', 'java',
            'go', 'rust', 'dotnet', 'aspnet',
            'wordpress', 'joomla', 'drupal', 'magento',
            'shopify', 'woocommerce', 'prestashop',
            'sharepoint', 'dynamics', 'salesforce',
            'zendesk', 'freshdesk', 'helpdesk',
            'sentry', 'rollbar', 'bugsnag', 'airbrake',
            'newrelic', 'datadog', 'appdynamics',
            'splunk', 'sumologic', 'loggly', 'papertrail',
        ]
        
        # וריאציות עם הדומיין
        variations = []
        for sub in common:
            variations.extend([
                sub,
                f"{sub}1",
                f"{sub}2",
                f"{sub}01",
                f"{sub}-01",
                f"{sub}-prod",
                f"{sub}-production",
                f"{sub}-live",
                f"{sub}-new",
                f"{sub}-old",
                f"new-{sub}",
                f"old-{sub}",
                f"prod-{sub}",
            ])
        
        return list(set(variations))
    
    def print_status(self, message, status="info"):
        """הדפסה עם צבעים לפי סטטוס"""
        if COLORS:
            if status == "success":
                print(f"{Fore.GREEN}[+] {message}")
            elif status == "warning":
                print(f"{Fore.YELLOW}[!] {message}")
            elif status == "error":
                print(f"{Fore.RED}[-] {message}")
            elif status == "info":
                print(f"{Fore.CYAN}[*] {message}")
            else:
                print(f"[*] {message}")
        else:
            print(f"[*] {message}")
    
    # ==================== שיטות DNS מתקדמות ====================
    
    def dns_resolve(self, subdomain):
        """רזולוציית DNS עם ניסיון מספר שרתים"""
        if not DNS_AVAILABLE:
            try:
                socket.gethostbyname(subdomain)
                return True, "system"
            except:
                return False, None
        
        for ns in self.nameservers:
            try:
                resolver = dns.resolver.Resolver()
                resolver.nameservers = [ns]
                resolver.timeout = 5
                resolver.lifetime = 5
                answers = resolver.resolve(subdomain, 'A')
                if answers:
                    return True, ns
            except:
                continue
        return False, None
    
    # ==================== מקורות פסיביים מתקדמים ====================
    
    def crt_sh_advanced(self):
        """חיפוש מתקדם ב-crt.sh עם פילטרים נוספים"""
        try:
            urls = [
                f"https://crt.sh/?q=%25.{self.domain}&output=json",
                f"https://crt.sh/?q={self.domain}&output=json",
                f"https://crt.sh/?q=*.{self.domain}&output=json",
            ]
            
            for url in urls:
                try:
                    response = self.session.get(url, timeout=self.timeout, verify=False)
                    if response.status_code == 200:
                        try:
                            data = response.json()
                            for cert in data:
                                # חיפוש בכל השדות הרלוונטיים
                                fields_to_check = ['name_value', 'common_name', 'subject_name']
                                for field in fields_to_check:
                                    if field in cert:
                                        values = cert[field]
                                        if isinstance(values, str):
                                            values = [values]
                                        for value in values:
                                            # חיפוש כל הסאב-דומיינים
                                            pattern = r'(?:[\w\.-]+\.)?[\w\.-]+\.' + re.escape(self.domain)
                                            matches = re.findall(pattern, value, re.IGNORECASE)
                                            for match in matches:
                                                self.subdomains.add(match.lower())
                        except json.JSONDecodeError:
                            # אם זה לא JSON, נחפש בטקסט
                            pattern = r'[\w\.-]+\.' + re.escape(self.domain)
                            matches = re.findall(pattern, response.text, re.IGNORECASE)
                            for match in matches:
                                self.subdomains.add(match.lower())
                except Exception as e:
                    self.print_status(f"Error accessing crt.sh: {e}", "error")
                    continue
                
                time.sleep(0.5)  # הגבלת rate
        except Exception as e:
            self.print_status(f"Error in crt.sh: {e}", "error")
    
    def hackertarget_dns(self):
        """שימוש ב-HackerTarget DNS API (חינמי)"""
        try:
            url = f"https://api.hackertarget.com/hostsearch/?q={self.domain}"
            response = self.session.get(url, timeout=self.timeout, verify=False)
            
            if response.status_code == 200:
                lines = response.text.strip().split('\n')
                for line in lines:
                    if ',' in line:
                        subdomain = line.split(',')[0].strip()
                        if subdomain and self.domain in subdomain:
                            self.subdomains.add(subdomain.lower())
        except Exception as e:
            self.print_status(f"Error in HackerTarget: {e}", "error")
    
    def anubis_db(self):
        """חיפוש ב-AnubisDB (מאגר של subdomains)"""
        try:
            url = f"https://jonlu.ca/anubis/subdomains/{self.domain}"
            response = self.session.get(url, timeout=self.timeout, verify=False)
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    for subdomain in data:
                        if isinstance(subdomain, str):
                            self.subdomains.add(subdomain.lower())
                except:
                    # נסה לפרש כטקסט
                    pattern = r'[\w\.-]+\.' + re.escape(self.domain)
                    matches = re.findall(pattern, response.text, re.IGNORECASE)
                    for match in matches:
                        self.subdomains.add(match.lower())
        except Exception as e:
            self.print_status(f"Error in AnubisDB: {e}", "error")
    
    def threatcrowd(self):
        """חיפוש ב-ThreatCrowd API"""
        try:
            url = f"https://threatcrowd.org/searchApi/v2/domain/report/?domain={self.domain}"
            response = self.session.get(url, timeout=self.timeout, verify=False)
            
            if response.status_code == 200:
                data = response.json()
                # חיפוש בסאב-דומיינים
                if 'subdomains' in data:
                    for subdomain in data['subdomains']:
                        if isinstance(subdomain, str):
                            self.subdomains.add(subdomain.lower())
                
                # חיפוש ב-resolutions
                if 'resolutions' in data:
                    for resolution in data['resolutions']:
                        if isinstance(resolution, dict) and 'domain' in resolution:
                            self.subdomains.add(resolution['domain'].lower())
        except Exception as e:
            self.print_status(f"Error in ThreatCrowd: {e}", "error")
    
    def rapiddns(self):
        """חיפוש ב-RapidDNS"""
        try:
            url = f"https://rapiddns.io/subdomain/{self.domain}?full=1"
            response = self.session.get(url, timeout=self.timeout, verify=False)
            
            if response.status_code == 200:
                # שימוש ב-BeautifulSoup לפרסון HTML
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # חיפוש בטבלאות
                tables = soup.find_all('table')
                for table in tables:
                    rows = table.find_all('tr')
                    for row in rows:
                        cols = row.find_all('td')
                        if len(cols) >= 1:
                            subdomain = cols[0].text.strip()
                            if subdomain and self.domain in subdomain:
                                self.subdomains.add(subdomain.lower())
                
                # חיפוש נוסף באמצעות regex
                pattern = r'[\w\.-]+\.' + re.escape(self.domain)
                matches = re.findall(pattern, response.text, re.IGNORECASE)
                for match in matches:
                    self.subdomains.add(match.lower())
        except Exception as e:
            self.print_status(f"Error in RapidDNS: {e}", "error")
    
    def dnsbufferoverrun(self):
        """חיפוש ב-DNS Buffer Overrun"""
        try:
            url = f"https://dns.bufferover.run/dns?q=.{self.domain}"
            response = self.session.get(url, timeout=self.timeout, verify=False)
            
            if response.status_code == 200:
                data = response.json()
                if 'FDNS_A' in data:
                    records = data['FDNS_A']
                    for record in records:
                        if isinstance(record, str):
                            if ',' in record:
                                parts = record.split(',')
                                for part in parts:
                                    if self.domain in part:
                                        self.subdomains.add(part.strip().lower())
                            else:
                                if self.domain in record:
                                    self.subdomains.add(record.strip().lower())
        except Exception as e:
            self.print_status(f"Error in DNS Buffer Overrun: {e}", "error")
    
    def find_subdomains_from_js(self):
        """חיפוש סאב-דומיינים בקובצי JavaScript"""
        try:
            # ראשית, נשיג את הדף הראשי
            main_url = f"http://{self.domain}"
            try:
                response = self.session.get(main_url, timeout=self.timeout, verify=False)
                if response.status_code == 200:
                    # חיפוב קישורים ל-JS files
                    soup = BeautifulSoup(response.text, 'html.parser')
                    js_links = []
                    
                    # קישורי script
                    for script in soup.find_all('script'):
                        src = script.get('src')
                        if src:
                            full_url = urljoin(main_url, src)
                            js_links.append(full_url)
                    
                    # סריקת קובצי JS (מוגבל ל-3 קבצים למהירות)
                    for js_url in js_links[:3]:
                        try:
                            js_response = self.session.get(js_url, timeout=10, verify=False)
                            if js_response.status_code == 200:
                                # חיפוש דומיינים בטקסט
                                pattern = r'(?:https?://)?([\w\.-]+\.' + re.escape(self.domain) + ')'
                                matches = re.findall(pattern, js_response.text)
                                for match in matches:
                                    self.subdomains.add(match.lower())
                        except:
                            continue
            except:
                pass
        except Exception as e:
            self.print_status(f"Error in JS analysis: {e}", "error")
    
    # ==================== שיטות אקטיביות מתקדמות ====================
    
    def dns_bruteforce_advanced(self, wordlist=None):
        """Brute Force מתקדם עם הגיוון"""
        if wordlist is None:
            wordlist = self.common_subdomains
        
        self.print_status(f"Starting DNS brute force with {len(wordlist)} words", "info")
        
        # הגבלה למהירות ב-fast mode
        if len(wordlist) > 500:
            wordlist = wordlist[:500]
        
        total_found = 0
        
        def check_subdomain(subdomain):
            result, ns = self.dns_resolve(subdomain)
            if result:
                return subdomain, ns
            return None, None
        
        with ThreadPoolExecutor(max_workers=self.threads) as executor:
            futures = []
            for word in wordlist:
                subdomain = f"{word}.{self.domain}"
                futures.append(executor.submit(check_subdomain, subdomain))
            
            if TQDM_AVAILABLE:
                for future in tqdm(as_completed(futures), total=len(futures), desc="Brute forcing"):
                    subdomain, ns = future.result()
                    if subdomain:
                        self.subdomains.add(subdomain.lower())
                        total_found += 1
            else:
                for i, future in enumerate(as_completed(futures)):
                    subdomain, ns = future.result()
                    if subdomain:
                        self.subdomains.add(subdomain.lower())
                        total_found += 1
                    if i % 50 == 0:
                        self.print_status(f"Checked {i}/{len(futures)} words, found {total_found} subdomains", "info")
        
        self.print_status(f"Brute force found {total_found} new subdomains", "success")
    
    def dns_axfr_advanced(self):
        """ניסיון DNS Zone Transfer עם מספר שרתים"""
        if not DNS_AVAILABLE:
            self.print_status("DNS AXFR requires dnspython library", "warning")
            return
        
        self.print_status("Attempting DNS Zone Transfer", "info")
        
        try:
            # קבלת name servers של הדומיין
            resolver = dns.resolver.Resolver()
            resolver.nameservers = self.nameservers
            
            # נסה מספר סוגי רשומות
            record_types = ['NS', 'SOA']
            
            for record_type in record_types:
                try:
                    answers = resolver.resolve(self.domain, record_type)
                    for answer in answers:
                        ns_server = str(answer).rstrip('.')
                        self.print_status(f"Found {record_type}: {ns_server}", "info")
                        
                        # נסה AXFR
                        try:
                            zone = dns.zone.from_xfr(dns.query.xfr(ns_server, self.domain))
                            if zone:
                                self.print_status(f"AXFR successful on {ns_server}!", "success")
                                for name in zone.nodes.keys():
                                    subdomain = f"{name}.{self.domain}"
                                    self.subdomains.add(subdomain.lower())
                                break
                        except:
                            continue
                except:
                    continue
        except Exception as e:
            self.print_status(f"AXFR error: {e}", "error")
    
    def search_engines_dorking(self):
        """חיפוש באמצעות מנועי חיפוש (דורקינג)"""
        self.print_status("Searching via search engines", "info")
        
        dorks = [
            f"site:*.{self.domain}",
            f"inurl:{self.domain}",
        ]
        
        search_engines = [
            ("https://www.google.com/search?q=", 50),
            ("https://duckduckgo.com/html/?q=", 30),
        ]
        
        for dork in dorks:
            for engine_base, limit in search_engines:
                try:
                    url = f"{engine_base}{dork}"
                    response = self.session.get(url, timeout=self.timeout, verify=False)
                    
                    if response.status_code == 200:
                        # חיפוש בדומיינים בתוצאות
                        pattern = r'(?:https?://)?([\w\.-]+\.' + re.escape(self.domain) + ')'
                        matches = re.findall(pattern, response.text)
                        
                        for match in matches:
                            if match.count('.') >= 2:  # רק סאב-דומיינים אמיתיים
                                self.subdomains.add(match.lower())
                        
                        # הגבלת התוצאות
                        if len(matches) > limit:
                            break
                except Exception as e:
                    self.print_status(f"Search engine error: {e}", "error")
                    continue
                
                time.sleep(1)  # הגבלת rate
    
    # ==================== שיטות וולידציה ====================
    
    def validate_all_subdomains(self):
        """וולידציה של כל הסאב-דומיינים"""
        self.print_status(f"Validating {len(self.subdomains)} subdomains", "info")
        
        valid_subs = set()
        
        def validate_sub(subdomain):
            try:
                socket.gethostbyname(subdomain)
                return subdomain
            except socket.gaierror:
                return None
            except:
                return None
        
        subdomains_list = list(self.subdomains)
        
        if TQDM_AVAILABLE:
            with ThreadPoolExecutor(max_workers=self.threads) as executor:
                results = list(tqdm(
                    executor.map(validate_sub, subdomains_list),
                    total=len(subdomains_list),
                    desc="Validating"
                ))
                for result in results:
                    if result:
                        valid_subs.add(result)
        else:
            self.print_status(f"Processing {len(subdomains_list)} subdomains...", "info")
            with ThreadPoolExecutor(max_workers=self.threads) as executor:
                futures = {executor.submit(validate_sub, sub): sub for sub in subdomains_list}
                
                for i, future in enumerate(as_completed(futures)):
                    result = future.result()
                    if result:
                        valid_subs.add(result)
                    
                    if i % 50 == 0:
                        self.print_status(f"Validated {i}/{len(subdomains_list)}", "info")
        
        self.validated_subs = valid_subs
        self.print_status(f"Validation complete: {len(valid_subs)} valid subdomains", "success")
    
    # ==================== הרצה ראשית ====================
    
    def run_passive_enumeration(self):
        """הרצת כל השיטות הפסיביות"""
        self.print_status("Starting passive enumeration", "info")
        
        passive_methods = [
            self.crt_sh_advanced,
            self.hackertarget_dns,
            self.anubis_db,
            self.threatcrowd,
            self.rapiddns,
            self.dnsbufferoverrun,
            self.search_engines_dorking,
            self.find_subdomains_from_js,
        ]
        
        # הרצה עם תזמון
        for method in passive_methods:
            try:
                method_name = method.__name__
                self.print_status(f"Running {method_name}", "info")
                method()
                # השהייה בין בקשות
                time.sleep(1)
            except Exception as e:
                self.print_status(f"Method {method.__name__} failed: {e}", "error")
                continue
        
        self.print_status(f"Passive enumeration found {len(self.subdomains)} unique subdomains", "success")
    
    def run_active_enumeration(self, custom_wordlist=None):
        """הרצת כל השיטות האקטיביות"""
        self.print_status("Starting active enumeration", "info")
        
        # טעינת wordlist
        wordlist = self.common_subdomains
        if custom_wordlist and os.path.exists(custom_wordlist):
            try:
                with open(custom_wordlist, 'r') as f:
                    custom_words = [line.strip() for line in f if line.strip()]
                wordlist.extend(custom_words)
                wordlist = list(set(wordlist))  # הסרת כפילויות
                self.print_status(f"Loaded {len(custom_words)} words from custom wordlist", "success")
            except Exception as e:
                self.print_status(f"Could not read wordlist: {e}", "error")
        
        # הרצת השיטות האקטיביות
        self.dns_axfr_advanced()
        time.sleep(1)
        
        self.dns_bruteforce_advanced(wordlist)
        
        self.print_status(f"Active enumeration completed. Total: {len(self.subdomains)} subdomains", "success")
    
    def find_hidden_subdomains(self):
        """חיפוש סאב-דומיינים מוסתרים"""
        self.print_status("Looking for hidden subdomains", "info")
        
        # יצירת וריאציות נוספות מהסאב-דומיינים שכבר נמצאו
        base_subs = []
        for sub in list(self.subdomains):
            if f".{self.domain}" in sub:
                base = sub.replace(f".{self.domain}", "")
                if base and len(base) < 50:  # הגבלה לאורך סביר
                    base_subs.append(base)
        
        # וריאציות עם תווים מיוחדים
        variations = []
        prefixes = ['dev-', 'test-', 'staging-', 'prod-', 'uat-', 'qa-']
        suffixes = ['-dev', '-test', '-stage', '-prod', '-staging']
        
        for base in base_subs[:20]:  # מגבילים ל-20 בסיסים
            for prefix in prefixes:
                variations.append(f"{prefix}{base}")
            for suffix in suffixes:
                variations.append(f"{base}{suffix}")
        
        # בדיקת הווריאציות
        for variation in variations:
            subdomain = f"{variation}.{self.domain}"
            if subdomain not in self.subdomains:
                try:
                    socket.gethostbyname(subdomain)
                    self.subdomains.add(subdomain.lower())
                    self.print_status(f"Found hidden: {subdomain}", "success")
                except:
                    pass
        
        self.print_status(f"Hidden subdomain search completed", "success")
    
    def save_results(self):
        """שמירת התוצאות"""
        if not self.validated_subs:
            self.validate_all_subdomains()
        
        # סינון ומיון
        final_subs = sorted(self.validated_subs)
        
        # הצגה
        print(f"\n{'='*60}")
        print(f"FINAL RESULTS: {len(final_subs)} validated subdomains")
        print('='*60)
        
        for i, sub in enumerate(final_subs, 1):
            if COLORS:
                print(f"{Fore.GREEN}{i:4}. {sub}")
            else:
                print(f"{i:4}. {sub}")
        
        # שמירה לקובץ
        if self.output_file:
            try:
                with open(self.output_file, 'w') as f:
                    for sub in final_subs:
                        f.write(sub + '\n')
                
                # שמירת גרסה עם כל הסאב-דומיינים (כולל לא מאומתים)
                all_subs_file = self.output_file.replace('.txt', '_all.txt')
                if '.' not in os.path.basename(self.output_file):
                    all_subs_file = self.output_file + '_all.txt'
                    
                with open(all_subs_file, 'w') as f:
                    for sub in sorted(self.subdomains):
                        f.write(sub + '\n')
                
                self.print_status(f"Results saved to {self.output_file}", "success")
                self.print_status(f"All subdomains saved to {all_subs_file}", "info")
            except Exception as e:
                self.print_status(f"Error saving files: {e}", "error")
        else:
            # אם לא צוין קובץ פלט, נשמור לקובץ ברירת מחדל
            default_file = f"subdomains_{self.domain}.txt"
            with open(default_file, 'w') as f:
                for sub in final_subs:
                    f.write(sub + '\n')
            self.print_status(f"Results saved to {default_file}", "success")
    
    def run(self, passive=True, active=True, validate=True, wordlist=None):
        """הרצת כל התהליך"""
        if COLORS:
            banner = f"""{Fore.CYAN}
╔══════════════════════════════════════════════════════════╗
║               subrecon.py - Advanced Subdomain Finder    ║
║                    No API Required                       ║
╚══════════════════════════════════════════════════════════╝
{Fore.WHITE}Target: {Fore.YELLOW}{self.domain}
{Fore.WHITE}Threads: {Fore.YELLOW}{self.threads}
{Fore.CYAN}══════════════════════════════════════════════════════════{Fore.RESET}
            """
        else:
            banner = f"""
╔══════════════════════════════════════════════════════════╗
║               subrecon.py - Advanced Subdomain Finder    ║
║                    No API Required                       ║
╚══════════════════════════════════════════════════════════╝
Target: {self.domain}
Threads: {self.threads}
══════════════════════════════════════════════════════════
            """
        
        print(banner)
        
        start_time = time.time()
        
        # שלב 1: איסוף פסיבי
        if passive:
            self.run_passive_enumeration()
        
        # שלב 2: איסוף אקטיבי
        if active:
            self.run_active_enumeration(wordlist)
        
        # שלב 3: חיפוש סאב-דומיינים מוסתרים
        self.find_hidden_subdomains()
        
        # שלב 4: וולידציה
        if validate:
            self.validate_all_subdomains()
        else:
            self.validated_subs = self.subdomains
        
        # שלב 5: תוצאות
        self.save_results()
        
        end_time = time.time()
        elapsed = end_time - start_time
        
        if COLORS:
            print(f"\n{Fore.CYAN}{'='*70}")
            print(f"{Fore.GREEN}SCAN COMPLETED!")
            print(f"{Fore.WHITE}Total time: {Fore.YELLOW}{elapsed:.2f} seconds")
            print(f"{Fore.WHITE}Subdomains found: {Fore.YELLOW}{len(self.subdomains)}")
            print(f"{Fore.WHITE}Validated subdomains: {Fore.YELLOW}{len(self.validated_subs)}")
            print(f"{Fore.CYAN}{'='*70}{Fore.RESET}")
        else:
            print(f"\n{'='*70}")
            print(f"SCAN COMPLETED!")
            print(f"Total time: {elapsed:.2f} seconds")
            print(f"Subdomains found: {len(self.subdomains)}")
            print(f"Validated subdomains: {len(self.validated_subs)}")
            print(f"{'='*70}")

def main():
    parser = argparse.ArgumentParser(
        description='Advanced Subdomain Enumeration Tool - No API Required',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('domain', help='Target domain (e.g., example.com)')
    parser.add_argument('-o', '--output', help='Output file')
    parser.add_argument('-t', '--threads', type=int, default=20, help='Number of threads (default: 20)')
    parser.add_argument('-w', '--wordlist', help='Custom wordlist for brute force')
    parser.add_argument('--passive-only', action='store_true', help='Run only passive enumeration')
    parser.add_argument('--active-only', action='store_true', help='Run only active enumeration')
    parser.add_argument('--no-validate', action='store_true', help='Skip DNS validation')
    parser.add_argument('--fast', action='store_true', help='Fast mode (limited checks)')
    parser.add_argument('--timeout', type=int, default=30, help='Timeout in seconds (default: 30)')
    
    args = parser.parse_args()
    
    # התאמות ל-fast mode
    if args.fast:
        args.threads = min(args.threads, 10)
        args.timeout = 15
    
    # יצירת האובייקט
    enumerator = SubdomainEnumerator(
        domain=args.domain,
        output_file=args.output,
        threads=args.threads,
        timeout=args.timeout
    )
    
    # הרצה
    enumerator.run(
        passive=not args.active_only,
        active=not args.passive_only,
        validate=not args.no_validate,
        wordlist=args.wordlist
    )

if __name__ == "__main__":
    main()
