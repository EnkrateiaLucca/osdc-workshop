import curses
import pyperclip
import markdown
from bs4 import BeautifulSoup
import openai
import textwrap
from openai import OpenAI

client = OpenAI()


def parse_markdown(filename):
    with open(filename, 'r') as file:
        md_content = file.read()
    
    html = markdown.markdown(md_content)
    soup = BeautifulSoup(html, 'html.parser')
    
    sections = []
    current_section = ""
    current_title = ""
    
    for tag in soup.find_all(['h1', 'h2', 'h3', 'p']):
        if tag.name in ['h1', 'h2', 'h3']:
            if current_section:
                sections.append((current_title, current_section.strip()))
            current_title = tag.text
            current_section = tag.text + "\n\n"
        else:
            current_section += tag.text + "\n\n"
    
    if current_section:
        sections.append((current_title, current_section.strip()))
    
    return sections


SYS_MSG_REWRITE = """You are a helpful research assitant. Given a context document and a target section, rewrite it according to given instructions."""

def rewrite(context_document, section_to_rewrite, rewrite_instructions):
    prompt_rewrite = f"""Given this document I am working on: \n\n
    {context_document} \n\n, rewrite the text for this section: \n\n
    {section_to_rewrite} \n\n
    following these instructions: \n\n
    {rewrite_instructions} 
    """
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": SYS_MSG_REWRITE},
                  {"role": "user", "content": prompt_rewrite}]
    )
    
    return response.choices[0].message.content

def edit_text(stdscr, text):
    curses.echo()
    curses.curs_set(1)
    height, width = stdscr.getmaxyx()
    
    lines = text.split('\n')
    current_line = 0
    top_line = 0
    left_offset = 0
    
    while True:
        stdscr.clear()
        stdscr.addstr(0, 0, "Edit the text (Press Ctrl+G to save and exit):")
        
        for i in range(height - 3):
            if top_line + i < len(lines):
                line = lines[top_line + i][left_offset:left_offset+width-1]
                stdscr.addstr(i + 2, 0, line)
        
        try:
            cursor_y = min(current_line - top_line + 2, height - 1)
            cursor_x = min(len(lines[current_line]) - left_offset, width - 1)
            stdscr.move(cursor_y, cursor_x)
        except curses.error:
            pass
        
        stdscr.refresh()
        
        ch = stdscr.getch()
        
        if ch == ord('\n'):
            lines.insert(current_line + 1, '')
            current_line += 1
        elif ch == curses.KEY_BACKSPACE or ch == 127:
            if len(lines[current_line]) > 0:
                lines[current_line] = lines[current_line][:-1]
            elif current_line > 0:
                lines[current_line - 1] += lines.pop(current_line)
                current_line -= 1
        elif ch == curses.KEY_UP and current_line > 0:
            current_line -= 1
        elif ch == curses.KEY_DOWN and current_line < len(lines) - 1:
            current_line += 1
        elif ch == curses.KEY_LEFT and left_offset > 0:
            left_offset -= 1
        elif ch == curses.KEY_RIGHT:
            left_offset += 1
        elif ch == 7:  # Ctrl+G
            break
        elif 32 <= ch <= 126:
            lines[current_line] += chr(ch)
        
        if current_line < top_line:
            top_line = current_line
        elif current_line >= top_line + height - 3:
            top_line = current_line - height + 4
        
        # Adjust left_offset if cursor goes off-screen
        if len(lines[current_line]) - left_offset >= width:
            left_offset = len(lines[current_line]) - width + 1
        
    curses.noecho()
    curses.curs_set(0)
    return '\n'.join(lines)

def display_comparison(stdscr, original_title, original_content, new_content):
    curses.start_color()
    curses.init_pair(1, curses.COLOR_CYAN, curses.COLOR_BLACK)
    curses.init_pair(2, curses.COLOR_GREEN, curses.COLOR_BLACK)
    
    height, width = stdscr.getmaxyx()
    half_width = width // 2 - 2
    
    while True:
        stdscr.clear()
        stdscr.addstr(0, 0, "Original Section", curses.color_pair(1) | curses.A_BOLD)
        stdscr.addstr(0, half_width + 2, "AI-Generated Section", curses.color_pair(2) | curses.A_BOLD)
        stdscr.addstr(1, 0, original_title, curses.A_BOLD)
        stdscr.addstr(1, half_width + 2, "New Version", curses.A_BOLD)
        
        wrapped_original = textwrap.wrap(original_content, width=half_width)
        wrapped_new = textwrap.wrap(new_content, width=half_width)
        
        for i in range(min(height - 4, max(len(wrapped_original), len(wrapped_new)))):
            if i < len(wrapped_original):
                stdscr.addstr(i + 3, 0, wrapped_original[i], curses.color_pair(1))
            if i < len(wrapped_new):
                stdscr.addstr(i + 3, half_width + 2, wrapped_new[i], curses.color_pair(2))
        
        stdscr.addstr(height - 1, 0, "Press 'r' to replace, 'e' to edit, 'c' to copy new version, any other key to go back")
        stdscr.refresh()
        
        key = stdscr.getch()
        if key == ord('r'):
            return ("replace", new_content)
        elif key == ord('e'):
            edited_content = edit_text(stdscr, new_content)
            new_content = edited_content  # Update new_content with edited version
        elif key == ord('c'):
            pyperclip.copy(new_content)
            return "copied"
        else:
            return "back"

def get_user_instructions(stdscr):
    curses.echo()
    curses.curs_set(1)
    height, width = stdscr.getmaxyx()
    
    stdscr.clear()
    stdscr.addstr(0, 0, "Enter instructions for AI rewrite (press Enter when done):")
    stdscr.refresh()
    
    instructions = stdscr.getstr(2, 0, width - 1).decode('utf-8')
    
    curses.noecho()
    curses.curs_set(0)
    return instructions

def edit_menu(stdscr, section_title, section_content):
    curses.curs_set(0)
    stdscr.clear()
    
    options = [
        "Copy to clipboard",
        "Delete section",
        "Generate with AI and compare",
        "Replace section with clipboard",
        "Go back to navigation"
    ]
    
    current_option = 0
    
    while True:
        stdscr.clear()
        height, width = stdscr.getmaxyx()
        
        stdscr.addstr(0, 0, f"Editing: {section_title}", curses.A_BOLD)
        stdscr.addstr(2, 0, "Choose an action:")
        
        for i, option in enumerate(options):
            if i == current_option:
                stdscr.attron(curses.A_REVERSE)
            stdscr.addstr(i + 4, 2, option)
            stdscr.attroff(curses.A_REVERSE)
        
        key = stdscr.getch()
        
        if key == curses.KEY_UP and current_option > 0:
            current_option -= 1
        elif key == curses.KEY_DOWN and current_option < len(options) - 1:
            current_option += 1
        elif key == 10:  # Enter key
            if current_option == 0:
                pyperclip.copy(section_content)
                stdscr.addstr(height-1, 0, "Copied to clipboard!")
                stdscr.refresh()
                curses.napms(1000)
            elif current_option == 1:
                return "delete"
            elif current_option == 2:
                instructions = get_user_instructions(stdscr)
                if instructions:
                    rewritten = rewrite(section_content, section_title, instructions)
                    result = display_comparison(stdscr, section_title, section_content, rewritten)
                    if result == "copied":
                        stdscr.addstr(height-1, 0, "AI-generated content copied to clipboard!")
                        stdscr.refresh()
                        curses.napms(1000)
                    elif isinstance(result, tuple) and result[0] == "replace":
                        return result
                else:
                    stdscr.addstr(height-1, 0, "No instructions provided. Cancelled.")
                    stdscr.refresh()
                    curses.napms(1000)
            elif current_option == 3:
                new_content = pyperclip.paste()
                return ("replace", new_content)
            elif current_option == 4:
                return "back"
        
        stdscr.refresh()


def main(stdscr):
    curses.curs_set(0)
    stdscr.clear()
    
    filename = "./assets-resources/example-report-for-ui-testing.md"
    sections = parse_markdown(filename)
    current_section = 0
    
    while True:
        stdscr.clear()
        height, width = stdscr.getmaxyx()
        
        stdscr.addstr(0, 0, "Use arrow keys to navigate. Press Enter to edit. Press 'q' to quit.")
        
        # Display section content
        title, content = sections[current_section]
        lines = content.split('\n')
        for i, line in enumerate(lines[:height-3]):
            if i + 2 < height:
                stdscr.addstr(i + 2, 0, line[:width-1])
        
        # Highlight current section
        stdscr.attron(curses.A_REVERSE)
        stdscr.addstr(1, 0, f"Section {current_section + 1}/{len(sections)}: {title}")
        stdscr.attroff(curses.A_REVERSE)
        
        key = stdscr.getch()
        
        if key == ord('q'):
            break
        elif key == curses.KEY_UP and current_section > 0:
            current_section -= 1
        elif key == curses.KEY_DOWN and current_section < len(sections) - 1:
            current_section += 1
        elif key == 10:  # Enter key
            result = edit_menu(stdscr, title, content)
            if result == "delete":
                sections.pop(current_section)
                if current_section == len(sections):
                    current_section -= 1
            elif isinstance(result, tuple) and result[0] == "replace":
                sections[current_section] = (title, result[1])
        
        stdscr.refresh()
    
    # Save the modified document
    with open(filename, 'w') as f:
        for title, content in sections:
            f.write(f"# {title}\n\n{content}\n\n")

if __name__ == "__main__":
    curses.wrapper(main)