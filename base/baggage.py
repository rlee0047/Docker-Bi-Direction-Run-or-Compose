import shlex
import yaml
import argparse
import sys

def convert_docker_run_to_compose(run_command: str) -> str:
    """
    Converts a Docker run command to a Docker Compose YAML string.

    Args:
        run_command: A string containing the 'docker run' command.

    Returns:
        A string in YAML format for a docker-compose.yml file, or an error message.
    """
    # Remove the initial 'docker run' part for easier parsing
    if run_command.lower().startswith("docker run"):
        run_command = run_command[len("docker run"):].strip()

    # Use shlex to split the command string correctly, handling quotes
    try:
        args = shlex.split(run_command)
    except ValueError as e:
        return f"Error: Could not parse the command. Details: {e}"

    # Initialize the compose structure
    compose_data = {
        'version': '3.8',
        'services': {
            'myservice': {}  # Default service name
        }
    }
    
    service = compose_data['services']['myservice']
    
    # Use a custom argparse parser that doesn't exit on error
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
        # The remaining arguments will be the image and command
        parsed_args, remaining_args = parser.parse_known_args(args)
    except ValueError as e:
        return f"Error: Invalid argument found. Details: {e}"
    
    # Set the service name from the --name flag
    if parsed_args.name:
        service_name = parsed_args.name
        compose_data['services'][service_name] = service
        del compose_data['services']['myservice']
    
    # The first remaining argument is typically the image
    if remaining_args:
        service['image'] = remaining_args.pop(0)
    else:
        return "Error: No image specified in the docker run command."

    # The rest are the command/entrypoint
    if remaining_args:
        service['command'] = ' '.join(remaining_args)

    # Map parsed arguments to Docker Compose format
    if parsed_args.publish:
        service['ports'] = parsed_args.publish

    if parsed_args.volume:
        service['volumes'] = parsed_args.volume

    if parsed_args.env:
        service['environment'] = parsed_args.env

    if parsed_args.network:
        service['networks'] = [parsed_args.network]
        compose_data['networks'] = {
            parsed_args.network: {'external': True}
        }
        
    if parsed_args.restart:
        service['restart'] = parsed_args.restart

    # Convert the Python dictionary to a YAML formatted string
    return yaml.dump(compose_data, sort_keys=False, indent=2)

# --- Main execution block with continuous loop ---
if __name__ == "__main__":
    print("Docker Run to Compose Converter")
    print("Enter your 'docker run' command below, or type 'exit' or 'q' to quit.")
    print("-" * 60)

    while True:
        try:
            # Prompt the user to enter the docker run command
            prompt = "\n> "
            docker_command_input = input(prompt)
            
            # Check for exit condition
            if docker_command_input.lower() in ['exit', 'q', 'quit']:
                print("Goodbye!")
                break

            # Process the command if it's not empty
            if docker_command_input.strip():
                compose_output = convert_docker_run_to_compose(docker_command_input)
                print("\n--- Generated docker-compose.yml ---\n")
                print(compose_output)
            else:
                # If user enters nothing, just show the prompt again
                continue

        except KeyboardInterrupt:
            # Handle Ctrl+C gracefully
            print("\nOperation cancelled by user. Goodbye!")
            sys.exit(0)
