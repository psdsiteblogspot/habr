import requests
from bs4 import BeautifulSoup
import json
import time
from urllib.parse import urljoin
from datetime import datetime, timezone
import os
import schedule

# Настройки
BASE_URL = "https://career.habr.com"
SEARCH_URL = "https://career.habr.com/vacancies"
SEARCH_PARAMS = {
    "q": "Системный администратор",
    "s[]": ["17", "88"],
    "type": "all"
}
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}
DELAY = 2
DATA_FILE = 'habr_vacancies.json'
CHECK_INTERVAL = 60

def load_existing_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None

def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def parse_vacancy_list_page(url):
    time.sleep(DELAY)
    response = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(response.text, 'html.parser')
    
    vacancies = []
    for card in soup.select('.vacancy-card'):
        try:
            title_elem = card.select_one('.vacancy-card__title-link')
            company_elem = card.select_one('.vacancy-card__company-title a')
            salary_elem = card.select_one('.basic-salary')
            date_elem = card.select_one('.basic-date')
            location_elem = card.select_one('.vacancy-card__meta a')
            
            vacancy_url = urljoin(BASE_URL, title_elem['href'])
            
            vacancies.append({
                "id": vacancy_url.split('/')[-1],
                "name": title_elem.text.strip(),
                "company": company_elem.text.strip() if company_elem else "Не указано",
                "company_id": "Не указано",
                "company_url": urljoin(BASE_URL, company_elem['href']) if company_elem else "Не указано",
                "company_logo": card.select_one('.vacancy-card__icon img')['src'] if card.select_one('.vacancy-card__icon img') else "Не указано",
                "url": vacancy_url,
                "published_at": date_elem['datetime'] if date_elem else "",
                "created_at": date_elem['datetime'] if date_elem else "",
                "area": location_elem.text.strip() if location_elem else "Не указано",
                "salary": salary_elem.text.strip() if salary_elem else "Зарплата не указана",
                "salary_raw": salary_elem.text.strip() if salary_elem else None,
                "experience": "Не указано",
                "schedule": "Не указано",
                "employment": "Не указано",
                "requirement": "",
                "responsibility": "",
                "type": "Открытая",
                "professional_roles": ["Системный администратор"],
                "has_test": False,
                "premium": False,
                "accept_handicapped": False,
                "accept_kids": False,
                "accept_temporary": False
            })
        except Exception as e:
            print(f"Ошибка при парсинге карточки вакансии: {e}")
            continue
    
    next_page = soup.select_one('.button-comp--appearance-pagination-button[href]')
    next_page_url = urljoin(BASE_URL, next_page['href']) if next_page else None
    
    return vacancies, next_page_url

def parse_vacancy_details(url):
    time.sleep(DELAY)
    response = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(response.text, 'html.parser')
    
    details = {
        "experience": "Не указано",
        "schedule": "Не указано",
        "employment": "Не указано",
        "requirement": "",
        "responsibility": ""
    }
    
    try:
        description = soup.select_one('.vacancy-description__text')
        if description:
            details["responsibility"] = description.get_text(separator='\n').strip()
            details["requirement"] = description.get_text(separator='\n').strip()
        
        meta_info = soup.select('.content-section')
        for section in meta_info:
            title = section.select_one('.content-section__title')
            if not title:
                continue
                
            title_text = title.text.strip()
            if "Требования" in title_text:
                skills = section.select('.preserve-line')
                if skills:
                    details["requirement"] = "\n".join([skill.text.strip() for skill in skills])
            elif "Местоположение и тип занятости" in title_text:
                employment = section.select('.preserve-line')
                if employment and len(employment) > 1:
                    details["schedule"] = employment[1].text.strip()
                    details["employment"] = employment[1].text.strip()
    except Exception as e:
        print(f"Ошибка при парсинге деталей вакансии {url}: {e}")
    
    return details

def collect_statistics(vacancies):
    stats = {
        "total": len(vacancies),
        "with_salary": sum(1 for v in vacancies if v.get("salary_raw")),
        "companies": len(set(v.get("company") for v in vacancies)),
        "cities": len(set(v.get("area") for v in vacancies)),
        "premium": sum(1 for v in vacancies if v.get("premium")),
        "with_test": sum(1 for v in vacancies if v.get("has_test"))
    }
    return stats

def get_all_vacancies():
    all_vacancies = []
    current_url = f"{SEARCH_URL}?q={SEARCH_PARAMS['q']}&s[]={SEARCH_PARAMS['s[]'][0]}&s[]={SEARCH_PARAMS['s[]'][1]}&type={SEARCH_PARAMS['type']}"
    
    while current_url:
        print(f"Парсинг страницы: {current_url}")
        vacancies, next_page_url = parse_vacancy_list_page(current_url)
        
        for vacancy in vacancies:
            print(f"Парсинг деталей вакансии: {vacancy['url']}")
            details = parse_vacancy_details(vacancy['url'])
            vacancy.update(details)
        
        all_vacancies.extend(vacancies)
        current_url = next_page_url
    
    return all_vacancies

def check_new_vacancies():
    print(f"\n{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Проверка новых вакансий...")
    
    existing_data = load_existing_data()
    if not existing_data:
        print("Нет существующих данных, выполняется полный парсинг")
        full_parse()
        return
        
    current_vacancies = get_all_vacancies()
    
    existing_ids = {v['id'] for v in existing_data['vacancies']}
    new_vacancies = [v for v in current_vacancies if v['id'] not in existing_ids]
    
    if new_vacancies:
        print(f"Найдено {len(new_vacancies)} новых вакансий")
        existing_data['vacancies'] = new_vacancies + existing_data['vacancies']
        existing_data['statistics'] = collect_statistics(existing_data['vacancies'])
        existing_data['updated'] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        
        save_data(existing_data)
        print("Данные успешно обновлены")
    else:
        print("Новых вакансий не найдено")

def full_parse():
    print("Выполняется полный парсинг вакансий...")
    all_vacancies = get_all_vacancies()
    
    result = {
        "source": "career.habr.com",
        "search_keywords": [
            "системный администратор",
            "сисадмин",
            "system administrator"
        ],
        "search_params": {
            "area": "Россия",
            "schedule": "Удалённая работа",
            "search_field": "В названии вакансии"
        },
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "statistics": collect_statistics(all_vacancies),
        "vacancies": all_vacancies
    }
    
    save_data(result)
    print(f"Сохранено {len(all_vacancies)} вакансий в файл {DATA_FILE}")

def run_scheduler():
    print(f"Скрипт запущен. Проверка новых вакансий будет выполняться каждый час.")
    print(f"Следующая проверка в {datetime.now().strftime('%H:%M')}")
    
    schedule.every(CHECK_INTERVAL).minutes.do(check_new_vacancies)
    
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    if not os.path.exists(DATA_FILE):
        full_parse()
    
    run_scheduler()
