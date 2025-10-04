import shlex
import yaml
import argparse
import tkinter as tk
from tkinter import scrolledtext, font

# --- Core Conversion Logic (unchanged from the previous version) ---

def convert_docker_run_to_compose(run_command: str) -> str:
    """
    Converts a Docker run command to a Docker Compose YAML string.
    """
    if not run_command.lower().strip().startswith("docker run"):
        return "Error: Input must be a 'docker run' command."
        
    if run_command.lower().startswith("docker run"):
        run_command = run_command[len("docker run"):].strip()

    try:
        args = shlex.split(run_command)
    except ValueError as e:
        return f"Error: Could not parse the command. Details: {e}"

    compose_data = {'version': '3.8', 'services': {'myservice': {}}}
    service = compose_data['services']['myservice']
    
    class NonExitingArgumentParser(argparse.ArgumentParser):
        def error(self, message):
            raise ValueError(message)

    parser = NonExitingArgumentParser(add_help=False)
    parser.add_argument('-d', '--detach', action='store_true')
    parser.add_argument('--name', type=str)
    parser.add_argument('-p', '--publish', action='append', default=[])
    parser.add_argument('-v', '--volume', action='append', default=[])
    parser.add_argument('-e', '--env', action='append', default=[])
    parser.add_argument('--network', type=str)
    parser.add_argument('--restart', type=str)
    parser.add_argument('--rm', action='store_true')
    
    try:
        parsed_args, remaining_args = parser.parse_known_args(args)
    except ValueError as e:
        return f"Error: Invalid argument found. Details: {e}"
    
    if parsed_args.name:
        service_name = parsed_args.name
        compose_data['services'][service_name] = service
        del compose_data['services']['myservice']
    
    if remaining_args:
        service['image'] = remaining_args.pop(0)
    else:
        return "Error: No image specified in the docker run command."

    if remaining_args:
        service['command'] = ' '.join(remaining_args)

    if parsed_args.publish:
        service['ports'] = parsed_args.publish
    if parsed_args.volume:
        service['volumes'] = parsed_args.volume
    if parsed_args.env:
        service['environment'] = parsed_args.env
    if parsed_args.network:
        service['networks'] = [parsed_args.network]
        compose_data['networks'] = {parsed_args.network: {'external': True}}
    if parsed_args.restart:
        service['restart'] = parsed_args.restart

    return yaml.dump(compose_data, sort_keys=False, indent=2)


# --- GUI Application ---

class App(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("Docker Run to Compose Converter")
        self.geometry("800x650")

        # Configure styles
        self.configure(bg="#f0f0f0")
        default_font = font.nametofont("TkDefaultFont")
        default_font.configure(family="Arial", size=10)
        text_font = ("Consolas", 10)

        # --- Input Frame ---
        input_frame = tk.Frame(self, padx=10, pady=10, bg="#f0f0f0")
        input_frame.pack(fill=tk.X, side=tk.TOP)
        
        input_label = tk.Label(input_frame, text="Enter 'docker run' command below:", anchor="w", bg="#f0f0f0")
        input_label.pack(fill=tk.X)
        
        self.input_text = scrolledtext.ScrolledText(input_frame, height=8, wrap=tk.WORD, font=text_font)
        self.input_text.pack(fill=tk.BOTH, expand=True, pady=(5, 0))

        # --- Button Frame ---
        button_frame = tk.Frame(self, pady=10, bg="#f0f0f0")
        button_frame.pack(fill=tk.X)

        self.convert_button = tk.Button(
            button_frame, text="Convert ▶", command=self.perform_conversion, 
            bg="#2E8B57", fg="white", font=("Arial", 10, "bold")
        )
        self.convert_button.pack(side=tk.LEFT, padx=10)
        
        self.copy_button = tk.Button(
            button_frame, text="Copy to Clipboard 📋", command=self.copy_to_clipboard,
            bg="#4682B4", fg="white", font=("Arial", 10)
        )
        self.copy_button.pack(side=tk.LEFT, padx=10)

        self.status_label = tk.Label(button_frame, text="", fg="green", bg="#f0f0f0")
        self.status_label.pack(side=tk.LEFT, padx=10)


        # --- Output Frame ---
        # The fix: Removed padx and pady from the Frame constructor and moved them to pack()
        output_frame = tk.Frame(self, bg="#f0f0f0")
        output_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        output_label = tk.Label(output_frame, text="Generated docker-compose.yml:", anchor="w", bg="#f0f0f0")
        output_label.pack(fill=tk.X)

        self.output_text = scrolledtext.ScrolledText(
            output_frame, state='disabled', wrap=tk.WORD, 
            bg="#e0e0e0", font=text_font
        )
        self.output_text.pack(fill=tk.BOTH, expand=True, pady=(5, 0))

    def perform_conversion(self):
        """Gets input, calls the converter, and displays the output."""
        run_command = self.input_text.get("1.0", tk.END)
        if not run_command.strip():
            self.display_output("Please enter a command to convert.")
            return
            
        compose_output = convert_docker_run_to_compose(run_command)
        self.display_output(compose_output)
    
    def display_output(self, text):
        """Helper to display text in the output box."""
        self.output_text.config(state='normal')  # Enable writing
        self.output_text.delete("1.0", tk.END)
        self.output_text.insert(tk.END, text)
        self.output_text.config(state='disabled') # Disable writing

    def copy_to_clipboard(self):
        """Copies the content of the output box to the clipboard."""
        output_content = self.output_text.get("1.0", tk.END).strip()
        if output_content and "Error:" not in output_content:
            self.clipboard_clear()
            self.clipboard_append(output_content)
            self.status_label.config(text="Copied!")
            # Clear the message after 2 seconds
            self.after(2000, lambda: self.status_label.config(text=""))
        elif "Error:" in output_content:
            self.status_label.config(text="Cannot copy an error.")
            self.after(2000, lambda: self.status_label.config(text=""))
        else:
            self.status_label.config(text="Nothing to copy.")
            self.after(2000, lambda: self.status_label.config(text=""))


# --- Main execution block ---
if __name__ == "__main__":
    app = App()
    app.mainloop()
