class Actuator:
    def __init__(self, pipeline_id, device_id):
        self.pipeline_id = pipeline_id
        self.device_id = device_id
        self.status = "closed"  # Default state: closed
        
    def set_actuator(self, command):
        """
        Sets the actuator (valve) state based on command
        
        Args:
            command: String command ("open" or "close") or JSON with command info
        """
        import json
        
        try:
            # Try to parse as JSON
            if isinstance(command, str) and (command.startswith('{') and command.endswith('}')):
                cmd_data = json.loads(command)
                if "action" in cmd_data:
                    action = cmd_data["action"].lower()
                    # Check if command is for this specific device
                    target_pipeline = cmd_data.get("pipeline_id", self.pipeline_id)
                    target_device = cmd_data.get("device_id", self.device_id)
                    
                    if target_pipeline == self.pipeline_id and target_device == self.device_id:
                        if action in ["open", "close"]:
                            self.status = action
                            print(f"Actuator {self.pipeline_id}/{self.device_id} set to: {action}")
                        else:
                            print(f"Invalid action: {action}")
                    else:
                        print(f"Command not for this device. Target: {target_pipeline}/{target_device}")
            else:
                # Simple string command
                if command.lower() in ["open", "close"]:
                    self.status = command.lower()
                    print(f"Actuator {self.pipeline_id}/{self.device_id} set to: {command}")
                else:
                    print(f"Invalid command: {command}")
        except json.JSONDecodeError:
            print(f"Error decoding command: {command}")
        except Exception as e:
            print(f"Error processing command: {e}")
    
    def get_status(self):
        """Returns the current actuator status"""
        return self.status