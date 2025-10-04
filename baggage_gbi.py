import shlex
import yaml
import argparse
import tkinter as tk
from tkinter import scrolledtext, font

# --- Helper Functions for Input Detection ---

def determine_input_type(input_string: str) -> str:
    """
    Determines if the input is a 'docker run' command or a Docker Compose YAML.
    
    Returns:
        "docker_run", "docker_compose", or "unknown"
    """
    stripped_input = input_string.strip().lower()

    # 1. Check for docker run command
    if stripped_input.startswith("docker run"):
        return "docker_run"
    
    # 2. Check for Docker Compose YAML
    try:
        data = yaml.safe_load(input_string)
        # A valid compose file typically has 'version' and 'services' keys
        if isinstance(data, dict) and 'services' in data and data['services']:
            return "docker_compose"
    except yaml.YAMLError:
        pass # Not valid YAML

    return "unknown"


# --- Conversion Logic: RUN -> COMPOSE (Existing, slightly modified) ---

def convert_docker_run_to_compose(run_command: str) -> str:
    """
    Converts a Docker run command to a Docker Compose YAML string.
    """
    if not run_command.strip().lower().startswith("docker run"):
        # This path should technically not be hit if determine_input_type is called first,
        # but serves as a final safety check.
        return "Error: Input must be a 'docker run' command."
        
    run_command_bare = run_command[len("docker run"):].strip()

    try:
        # Use shlex to safely split the arguments, handling quotes and spaces
        args = shlex.split(run_command_bare)
    except ValueError as e:
        return f"Error: Could not parse the command using shlex. Details: {e}"

    compose_data = {'version': '3.8', 'services': {'myservice': {}}}
    service = compose_data['services']['myservice']
    
    # Custom ArgumentParser that raises an error instead of exiting the script
    class NonExitingArgumentParser(argparse.ArgumentParser):
        def error(self, message):
            raise ValueError(message)

    parser = NonExitingArgumentParser(add_help=False, prog='docker run')
    # Docker run arguments relevant to Compose
    parser.add_argument('-d', '--detach', action='store_true', help="Ignored in compose, but parsed.")
    parser.add_argument('--name', type=str)
    parser.add_argument('-p', '--publish', action='append', default=[])
    parser.add_argument('-v', '--volume', action='append', default=[])
    parser.add_argument('-e', '--env', action='append', default=[])
    parser.add_argument('--network', type=str)
    parser.add_argument('--restart', type=str)
    parser.add_argument('--rm', action='store_true', help="Ignored in compose, but parsed.")
    
    try:
        parsed_args, remaining_args = parser.parse_known_args(args)
    except ValueError as e:
        return f"Error: Invalid argument found in 'docker run' command. Details: {e}"
    
    # Rename service based on --name
    service_name = 'myservice'
    if parsed_args.name:
        service_name = parsed_args.name
        compose_data['services'][service_name] = service
        del compose_data['services']['myservice']
    
    # Image must be the first remaining argument
    if remaining_args:
        service['image'] = remaining_args.pop(0)
    else:
        return "Error: No image specified in the docker run command."

    # Remaining arguments become the 'command'
    if remaining_args:
        # Rejoin and then use shlex.split to maintain structure/quotes for exec form
        # However, for simplicity and common use case, we join it as a shell string.
        # This part assumes shell form: command: "some arguments"
        service['command'] = ' '.join(remaining_args)

    # Map flags to Compose keys
    if parsed_args.publish:
        service['ports'] = parsed_args.publish
    if parsed_args.volume:
        service['volumes'] = parsed_args.volume
    if parsed_args.env:
        service['environment'] = parsed_args.env
    if parsed_args.network:
        service['networks'] = [parsed_args.network]
        # Define external network for connection
        compose_data['networks'] = {parsed_args.network: {'external': True}}
    if parsed_args.restart:
        service['restart'] = parsed_args.restart

    return yaml.dump(compose_data, sort_keys=False, indent=2)


# --- Conversion Logic: COMPOSE -> RUN (New) ---

def convert_compose_to_docker_run(compose_yaml: str) -> str:
    """
    Converts a Docker Compose YAML string (first service) to a Docker run command.
    """
    try:
        data = yaml.safe_load(compose_yaml)
    except yaml.YAMLError as e:
        return f"Error: Invalid YAML format. Details: {e}"

    if not isinstance(data, dict) or 'services' not in data or not data['services']:
        return "Error: Invalid Docker Compose structure (missing 'services' or services are empty)."

    # Get the name and config of the FIRST service found
    service_name, service = next(iter(data['services'].items()))

    if 'image' not in service:
        return f"Error: Service '{service_name}' is missing the required 'image' field."

    run_parts = ["docker", "run"]
    
    # 1. Name (--name)
    run_parts.extend(["--name", service_name])

    # 2. Restart (--restart)
    if service.get('restart'):
        run_parts.extend(["--restart", service['restart']])

    # 3. Ports (-p)
    if service.get('ports'):
        for port_mapping in service['ports']:
            run_parts.extend(["-p", port_mapping])

    # 4. Volumes (-v)
    if service.get('volumes'):
        for volume_mapping in service['volumes']:
            run_parts.extend(["-v", volume_mapping])

    # 5. Environment (-e)
    if service.get('environment'):
        environment = service['environment']
        if isinstance(environment, dict):
            for key, value in environment.items():
                run_parts.extend(["-e", f"{key}={value}"])
        elif isinstance(environment, list):
             for env_var in environment:
                run_parts.extend(["-e", env_var])

    # 6. Networks (--network)
    if service.get('networks'):
        # For simplicity, use the first defined network
        network_name = service['networks']
        if isinstance(network_name, list) and network_name:
            run_parts.extend(["--network", network_name[0]])
        elif isinstance(network_name, str):
            run_parts.extend(["--network", network_name])

    # 7. Image (mandatory)
    run_parts.append(service['image'])
    
    # 8. Command (optional)
    if service.get('command'):
        command = service['command']
        if isinstance(command, list):
            # Exec form: split list into parts
            run_parts.extend(command)
        elif isinstance(command, str):
            # Shell form: split string into parts
            run_parts.extend(shlex.split(command))

    # Use shlex.join to safely quote the resulting command parts
    return shlex.join(run_parts)


# --- GUI Application ---

class App(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("Docker Command Bidirectional Converter")
        self.geometry("800x650")

        # Configure styles
        self.configure(bg="#f0f0f0")
        default_font = font.nametofont("TkDefaultFont")
        default_font.configure(family="Arial", size=10)
        text_font = ("Consolas", 10)

        # --- Input Frame ---
        input_frame = tk.Frame(self, padx=10, pady=10, bg="#f0f0f0")
        input_frame.pack(fill=tk.X, side=tk.TOP)
        
        self.input_label = tk.Label(
            input_frame, 
            text="Enter 'docker run' command OR 'docker compose' below:", 
            anchor="w", 
            bg="#f0f0f0",
            font=("Arial", 10, "bold")
        )
        self.input_label.pack(fill=tk.X)
        
        self.input_text = scrolledtext.ScrolledText(input_frame, height=8, wrap=tk.WORD, font=text_font, bd=1, relief=tk.SUNKEN)
        self.input_text.pack(fill=tk.BOTH, expand=True, pady=(5, 0))

        # --- Button Frame ---
        button_frame = tk.Frame(self, pady=10, bg="#f0f0f0")
        button_frame.pack(fill=tk.X)

        self.convert_button = tk.Button(
            button_frame, text="Convert ▶", command=self.perform_conversion, 
            bg="#2E8B57", fg="white", font=("Arial", 10, "bold"), activebackground="#3CB371"
        )
        self.convert_button.pack(side=tk.LEFT, padx=10)
        
        self.copy_button = tk.Button(
            button_frame, text="Copy Output 📋", command=self.copy_to_clipboard,
            bg="#4682B4", fg="white", font=("Arial", 10), activebackground="#5F9EA0"
        )
        self.copy_button.pack(side=tk.LEFT, padx=10)

        self.status_label = tk.Label(button_frame, text="Ready.", fg="#333", bg="#f0f0f0", font=("Arial", 10, "italic"))
        self.status_label.pack(side=tk.LEFT, padx=10)


        # --- Output Frame ---
        output_frame = tk.Frame(self, bg="#f0f0f0")
        output_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        self.output_label = tk.Label(output_frame, text="Conversion Output:", anchor="w", bg="#f0f0f0", font=("Arial", 10, "bold"))
        self.output_label.pack(fill=tk.X)

        self.output_text = scrolledtext.ScrolledText(
            output_frame, state='disabled', wrap=tk.WORD, 
            bg="#e0e0e0", font=text_font, bd=1, relief=tk.SUNKEN
        )
        self.output_text.pack(fill=tk.BOTH, expand=True, pady=(5, 0))

    def update_status(self, text, color="black"):
        """Helper to update the status bar."""
        self.status_label.config(text=text, fg=color)
        # Clear the message after 3 seconds, unless it's an error
        if "Error" not in text:
            self.after(3000, lambda: self.status_label.config(text="", fg="#333"))

    def update_output_label(self, text):
        """Helper to update the output box title."""
        self.output_label.config(text=text)

    def display_output(self, text):
        """Helper to display text in the output box."""
        self.output_text.config(state='normal')  # Enable writing
        self.output_text.delete("1.0", tk.END)
        self.output_text.insert(tk.END, text)
        self.output_text.config(state='disabled') # Disable writing

    def perform_conversion(self):
        """Gets input, determines type, calls the correct converter, and displays the output."""
        input_string = self.input_text.get("1.0", tk.END).strip()

        if not input_string:
            self.display_output("Nothing to convert! oof")
            self.update_status("Where's the beef?", color="red")
            return
            
        input_type = determine_input_type(input_string)
        output_text = ""
        conversion_direction = ""
        
        if input_type == "docker_run":
            output_text = convert_docker_run_to_compose(input_string)
            conversion_direction = "Run → Compose"
            self.update_output_label("Generated Docker Compose YAML:")
        elif input_type == "docker_compose":
            output_text = convert_compose_to_docker_run(input_string)
            conversion_direction = "Compose → Run"
            self.update_output_label("Generated **Docker Run** command:")
        else:
            output_text = "Error: Input is neither a recognizable 'Docker Run' command nor a Docker Compose YAML structure."
            conversion_direction = "Unknown"
            self.update_output_label("Conversion Output:")

        self.display_output(output_text)
        
        if "Error:" in output_text:
            self.update_status(f"Conversion failed ({conversion_direction}).", color="red")
        else:
            self.update_status(f"Conversion successful: {conversion_direction}", color="green")


    def copy_to_clipboard(self):
        """Copies the content of the output box to the clipboard."""
        output_content = self.output_text.get("1.0", tk.END).strip()
        if output_content and "Error:" not in output_content:
            try:
                self.clipboard_clear()
                self.clipboard_append(output_content)
                self.update_status("Copied to clipboard!", color="blue")
            except tk.TclError:
                self.update_status("Error: Could not access clipboard.", color="red")
        elif "Error:" in output_content:
            self.update_status("Cannot copy an error message.", color="red")
        else:
            self.update_status("Nothing to copy.", color="orange")


# --- Main execution block ---
if __name__ == "__main__":
    app = App()
    app.mainloop()
