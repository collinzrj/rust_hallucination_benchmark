import requests
import json
import re
from datetime import datetime

def get_rust_questions(max_questions=200):
    """
    Fetch the most recent questions with the 'rust' tag from Stack Overflow.
    
    Args:
        max_questions: Maximum number of questions to fetch (default: 200)
    
    Returns:
        List of question dictionaries
    """
    base_url = "https://api.stackexchange.com/2.3/questions"
    all_questions = []
    page = 1
    page_size = 100  # Maximum allowed by API
    
    while len(all_questions) < max_questions:
        # Calculate how many questions we still need
        remaining = max_questions - len(all_questions)
        current_page_size = min(page_size, remaining)
        
        params = {
            "order": "desc",
            "sort": "creation",
            "tagged": "rust",
            "site": "stackoverflow",
            "page": page,
            "pagesize": current_page_size,
            "filter": "withbody"  # Filter that includes body field
        }
        
        try:
            response = requests.get(base_url, params=params)
            response.raise_for_status()
            data = response.json()
            
            questions = data.get("items", [])
            if not questions:
                break  # No more questions available
            
            all_questions.extend(questions)
            
            # Check if we've reached the end or got all we need
            if not data.get("has_more", False) or len(all_questions) >= max_questions:
                break
            
            page += 1
            
            # Respect rate limiting - API allows 300 requests per day
            # Adding a small delay to be respectful
            import time
            time.sleep(0.1)
            
        except requests.exceptions.RequestException as e:
            print(f"Error fetching questions: {e}")
            break
    
    return all_questions[:max_questions]


def format_question(question):
    """Format a question dictionary for display."""
    creation_date = datetime.fromtimestamp(question.get("creation_date", 0))
    return {
        "question_id": question.get("question_id"),
        "title": question.get("title"),
        "body": question.get("body", ""),  # Include question body
        "link": question.get("link"),
        "creation_date": creation_date.strftime("%Y-%m-%d %H:%M:%S"),
        "view_count": question.get("view_count", 0),
        "answer_count": question.get("answer_count", 0),
        "score": question.get("score", 0),
        "tags": question.get("tags", [])
    }


if __name__ == "__main__":
    print("Fetching the most recent 200 Rust questions from Stack Overflow...")
    questions = get_rust_questions(500)
    
    print(f"\nFetched {len(questions)} questions\n")
    
    # Display first 5 questions as examples
    print("Sample questions (first 5):")
    print("-" * 80)
    for i, q in enumerate(questions[:5], 1):
        formatted = format_question(q)
        print(f"\n{i}. {formatted['title']}")
        print(f"   ID: {formatted['question_id']}")
        print(f"   Created: {formatted['creation_date']}")
        print(f"   Score: {formatted['score']}, Answers: {formatted['answer_count']}, Views: {formatted['view_count']}")
        print(f"   Link: {formatted['link']}")
        print(f"   Tags: {', '.join(formatted['tags'])}")
        # Display question body (first 200 characters)
        body = formatted.get('body', '')
        if body:
            # Remove HTML tags for cleaner display (basic approach)
            body_text = re.sub(r'<[^>]+>', '', body)
            body_preview = body_text[:200] + "..." if len(body_text) > 200 else body_text
            print(f"   Body: {body_preview}")
    
    # Save to JSONL file (one JSON object per line)
    output_file = "rust_questions.jsonl"
    with open(output_file, "w", encoding="utf-8") as f:
        for question in questions:
            json_line = json.dumps(question, ensure_ascii=False)
            f.write(json_line + "\n")
    
    print(f"\n\nAll {len(questions)} questions saved to {output_file} (JSONL format)")

