import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import pytesseract
from PIL import ImageGrab
import keyboard
import os
import sys
import re
from datetime import datetime
import time
import ctypes
import difflib
import pathlib
import threading
from collections import deque
import json
import logging

# Add this at the very top of your file, right after imports
original_print = print  # Store the original print function

# Tesseract Configuration
TESSDATA_PREFIX = r'C:\Program Files\Tesseract-OCR\tessdata'
TESSERACT_CMD = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# Update on every published Version
VERSION = "v0.5.0-alpha 11/03/2025"

os.environ['TESSDATA_PREFIX'] = TESSDATA_PREFIX
pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD

class ScreenOCR:
    def __init__(self):
        print("Starting application...")
        
        print("Setting Tesseract paths...")
        
        print("Initializing CaptiOCR...")
        self.root = tk.Tk()
        self.root.title("CaptiOCR Tool")
        
        # Initialize variables first
        print("Setting variables...")
        self.capture_area = None
        self.running = False
        self.selection_window = None
        self.selected_lang = tk.StringVar()
        self.selected_lang.set("English")  # Set default language
        self.status_var = tk.StringVar(value="Ready")
        self.capture_thread = None
        self.debug_enabled = tk.BooleanVar(value=False)
        self.stop_event = threading.Event()
        self.thread_lock = threading.Lock()
        self.text_history = deque(maxlen=10)  # Only keep last 10 text captures
        self.use_caption_mode = tk.BooleanVar(value=False) 

        # Add tracking for window IDs to detect leaks
        self.window_counter = 0
        self.active_windows = set()
        self.selection_bindings = []
        
        # Create the output directory
        self.setup_output_directory()
        
        # Track the most recently processed file
        self.last_processed_file = None
        self.current_capture_timestamp = None
        self.debug_capture_saved = False
                
        # Capture initial window size
        self.root.update()  # Ensure window is drawn
        self.initial_window_width = self.root.winfo_width()
        self.initial_window_height = self.root.winfo_height()
            
        # Get DPI scaling using the improved method
        self.scale_factor = self.detect_dpi_scaling()
        print(f"Final scale factor: {self.scale_factor}")
        
        print("Getting screen info...")
        # Basic screen info
        self.screen_width = self.root.winfo_screenwidth()
        self.screen_height = self.root.winfo_screenheight()
        
        print("Setting window size...")
        # Set initial size
        window_width = 280
        window_height = 600
        x = (self.screen_width - window_width) // 2
        y = (self.screen_height - window_height) // 2
        self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")

        self.root.minsize(window_width, window_height)
        self.root.maxsize(window_width, window_height)
        
        print("Setting languages...")
        # Language list
        self.languages = [
            ("English", "eng"),
            ("Italian", "ita")
        ]
        
        print("Setting up UI...")
        self.setup_ui()
        # Set up logging to redirect print to log file
        self.setup_logging()
        
        print("Initialization complete.")
    
    def setup_output_directory(self):
        """Create 'captures' and 'config' directories in the same folder as the script"""
        try:
            # Get the path of the script
            if getattr(sys, 'frozen', False):
                # For compiled executables
                script_path = os.path.dirname(sys.executable)
            else:
                # For .py script
                script_path = os.path.dirname(os.path.abspath(__file__))
            
            # Create captures directory
            self.capture_dir = os.path.join(script_path, "captures")
            os.makedirs(self.capture_dir, exist_ok=True)
            print(f"Output directory set to: {self.capture_dir}")
            
            # Create config directory
            self.config_dir = os.path.join(script_path, "config")
            os.makedirs(self.config_dir, exist_ok=True)
            print(f"Config directory set to: {self.config_dir}")
            
            # Only try to log if debug_enabled exists
            if hasattr(self, 'debug_enabled'):
                self.log_debug(f"Output directory created at: {self.capture_dir}")
                self.log_debug(f"Config directory created at: {self.config_dir}")
        except Exception as e:
            print(f"Error creating directories: {str(e)}")
            # Fallback to current directory
            self.capture_dir = "captures"
            self.config_dir = "config"
            os.makedirs(self.capture_dir, exist_ok=True)
            os.makedirs(self.config_dir, exist_ok=True)
            
    def setup_logging(self):
        """Set up a logging system to redirect prints to a log file"""
        # This method no longer needs to redirect stdout since we do it at program start
        # Instead, it can just log that the application has started
        try:
            print(f"ScreenOCR initialization complete at {datetime.now()}")
        except Exception as e:
            print(f"Error in setup_logging: {str(e)}")

    def cleanup_logging(self):
        """Clean up logging resources (handled in main now)"""
        print(f"Logging ended at {datetime.now()}")
    
    def setup_ui(self):
        print("Creating main frame...")
        frame = ttk.Frame(self.root, padding="20")
        frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        print("Adding title...")
        # Title
        title = ttk.Label(frame, text="CaptiOCR Tool", font=("Arial", 20))
        title.grid(row=1, column=0, pady=10)

        print("Version " + VERSION)
        # Version
        version = ttk.Label(frame, text="Version {}".format(VERSION), font=("Arial", 10))
        version.grid(row=2, column=0, pady=10)
        
        print("Adding language selection...")
        # Language selection
        lang_frame = ttk.LabelFrame(frame, text="Select Language", padding="10")
        lang_frame.grid(row=3, column=0, pady=10, sticky=(tk.W, tk.E))
        
        combo = ttk.Combobox(lang_frame, textvariable=self.selected_lang)
        combo['values'] = [lang[0] for lang in self.languages]
        combo.current(0)
        combo.pack(pady=5, padx=10, fill='x')
        
        print("Adding debug checkbox...")
        # Debug checkbox
        debug_check = ttk.Checkbutton(frame, text="Enable Debug Logging", variable=self.debug_enabled)
        debug_check.grid(row=4, column=0, pady=5)
        
        print("Adding Live Caption Optimization checkbox...")
        caption_check = ttk.Checkbutton(frame, text="Live Caption Optimization", variable=self.use_caption_mode)
        caption_check.grid(row=5, column=0, pady=5)
        
        print("Adding preferences buttons...")
        # Add a frame for preferences buttons
        prefs_frame = ttk.Frame(frame)
        prefs_frame.grid(row=6, column=0, pady=5, sticky=(tk.W, tk.E))
        
        # Save preferences button
        save_prefs_btn = ttk.Button(
            prefs_frame, 
            text="Save Settings", 
            command=self.save_preferences_with_feedback
        )
        save_prefs_btn.pack(side=tk.LEFT, padx=2, expand=True, fill=tk.X)
        
        # Load preferences button
        load_prefs_btn = ttk.Button(
            prefs_frame, 
            text="Load Settings", 
            command=self.load_preferences_with_feedback
        )
        load_prefs_btn.pack(side=tk.RIGHT, padx=2, expand=True, fill=tk.X)
        
        print("Adding start button...")
        # Start button
        self.start_button = tk.Button(
            frame,
            text="Start (Select Area)",
            command=self.start_capture,
            bg="#4CAF50",  # Green background
            fg="white",
            font=("Arial", 11),
            relief=tk.FLAT,
            padx=10,
            pady=5,
            bd=0,
            activebackground="#0b7dda",
            cursor="hand2"
        )
        self.start_button.grid(row=7, column=0, pady=10)
        
        print("Adding status label...")
        # Status
        self.status_label = ttk.Label(frame, textvariable=self.status_var)
        self.status_label.grid(row=8, column=0, pady=10)
        
        print("Adding caption display area...")
        # Caption display area
        caption_frame = ttk.LabelFrame(frame, text="Captured Text", padding="10")
        caption_frame.grid(row=9, column=0, pady=5, sticky=(tk.W, tk.E))
        
        print("Adding instructions...")
        # Instructions
        instructions = """
        Instructions:
        1. Select language
        2. Click 'Start' and Drag the Area
            to Capture
        3. Press Enter to begin OCR
        4. Press Ctrl+Q / STOP to stop OCR
        5. Save Processed File As...
        """
        ttk.Label(frame, text=instructions, justify=tk.LEFT).grid(row=10, column=0, pady=20)
        
        # Configure grid
        frame.columnconfigure(0, weight=1)
        print("UI setup complete.")

    def get_ocr_config(self):
        """Best OCR Recognition - need improoving - """
        if self.use_caption_mode.get():
            # Live Caption best Parameters:
            # PSM 7: text as single line
            # OEM 1: Use LSTM engine
            return "--psm 7 --oem 1 -c preserve_interword_spaces=1"
        else:
            # General text standart config
            return ""  # Tesseract predefined
        
    def _get_similarity_threshold(self):
        """Extract the text similarity threshold value"""
        if hasattr(self, '_text_similarity_threshold'):
            return self._text_similarity_threshold
        return 0.8  # Default value
        
        if hasattr(self, 'has_significant_new_content'):
            # Extract threshold from the method if possible
            import inspect
            signature = inspect.signature(self.has_significant_new_content)
            if 'threshold' in signature.parameters:
                default_threshold = signature.parameters['threshold'].default
                threshold = default_threshold
        return threshold

    def _create_preferences_object(self, profile_name="default"):
        """Create a standardized preferences object"""
        return {
            'profile_name': profile_name,
            'language': self.selected_lang.get(),
            'debug_enabled': self.debug_enabled.get(),
            'text_similarity_threshold': self._get_similarity_threshold(),
            'saved_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

    def _save_preferences_to_file(self, prefs, filename):
        """Save preferences object to a file
        
        Args:
            prefs (dict): The preferences object to save
            filename (str): Full path to the target file
            
        Returns:
            tuple: (success, error_message)
        """
        try:
            with open(filename, 'w') as f:
                json.dump(prefs, f, indent=2)
            print(f"Preferences saved to: {filename}")
            return True, None
        except Exception as e:
            print(f"Error saving preferences: {str(e)}")
            return False, str(e)

    def _apply_preferences(self, prefs):
        """Apply loaded preferences to the application
        
        Args:
            prefs (dict): The preferences object to apply
        """
        if 'language' in prefs:
            self.selected_lang.set(prefs['language'])
            print(f"Set language to: {prefs['language']}")
        
        if 'debug_enabled' in prefs:
            self.debug_enabled.set(prefs['debug_enabled'])
            print(f"Set debug mode to: {prefs['debug_enabled']}")
        
        # Fix for the text_similarity_threshold - handle null values properly
        if 'text_similarity_threshold' in prefs and prefs['text_similarity_threshold'] is not None:
            self._text_similarity_threshold = prefs['text_similarity_threshold']
            print(f"Set text similarity threshold to: {prefs['text_similarity_threshold']}")
        else:
            # Set default value if preference is null or missing
            self._text_similarity_threshold = 0.8
            print(f"Set text similarity threshold to default value: 0.8")
        
    def save_preferences_with_feedback(self):
        """Save preferences with a user-specified name and visual feedback"""
        try:
            # Ask for a preferences profile name
            profile_name = simpledialog.askstring(
                "Save Settings Profile", 
                "Enter a name for this settings profile:",
                parent=self.root
            )
            
            # If user cancels or enters nothing, don't save
            if not profile_name:
                return
                    
            # Sanitize the profile name (remove special characters, spaces)
            profile_name = re.sub(r'[^\w\-]', '_', profile_name)
            
            # Create preferences data using helper method
            prefs = self._create_preferences_object(profile_name)
            
            # Create filename based on profile name - use config directory
            prefs_file = os.path.join(self.config_dir, f'{profile_name}_preferences.json')
            
            # Save to file using helper method
            success, error = self._save_preferences_to_file(prefs, prefs_file)
            
            if success:
                # Show success message
                messagebox.showinfo(
                    "Settings Saved", 
                    f"Your preferences have been saved as profile '{profile_name}'.\n\n"
                    f"To load these settings in future, use 'Load Settings' and select this profile."
                )
            else:
                # Show error message
                messagebox.showerror(
                    "Error Saving Settings", 
                    f"Failed to save preferences: {error}"
                )
        except Exception as e:
            # Show error message
            messagebox.showerror(
                "Error Saving Settings", 
                f"Failed to save preferences: {str(e)}"
            )

    def save_preferences(self):
        """Save current preferences to a default file (used during application shutdown)"""
        try:
            # Use a default name
            default_profile_name = "default"
            
            # Create preferences object using helper method
            prefs = self._create_preferences_object(default_profile_name)
            
            # Save to config directory
            prefs_file = os.path.join(self.config_dir, f'{default_profile_name}_preferences.json')
            self._save_preferences_to_file(prefs, prefs_file)
        except Exception as e:
            print(f"Error saving preferences: {str(e)}")

    def load_preferences_with_feedback(self):
        """Load preferences with option to select from different profiles"""
        try:
            # Get all preference files in the config directory
            prefs_files = [f for f in os.listdir(self.config_dir) 
                          if f.endswith('_preferences.json')]
            
            if not prefs_files:
                messagebox.showinfo(
                    "No Settings Found", 
                    "No saved preferences file found."
                )
                return
                
            # If only one file exists, load it directly
            if len(prefs_files) == 1:
                file_to_load = os.path.join(self.config_dir, prefs_files[0])
            else:
                # Create a dialog to select which profile to load
                profile_window = tk.Toplevel(self.root)
                profile_window.title("Select Settings Profile")
                profile_window.geometry("400x300")
                profile_window.transient(self.root)
                profile_window.grab_set()
                
                # Listbox to show available profiles
                frame = ttk.Frame(profile_window, padding="20")
                frame.pack(fill=tk.BOTH, expand=True)
                
                ttk.Label(frame, text="Choose a settings profile to load:").pack(pady=(0, 10))
                
                listbox = tk.Listbox(frame, width=50, height=10)
                listbox.pack(fill=tk.BOTH, expand=True, pady=10)
                
                # Add profiles to listbox with readable names
                for i, file in enumerate(prefs_files):
                    # Extract profile info if available
                    profile_path = os.path.join(self.config_dir, file)
                    try:
                        with open(profile_path, 'r') as f:
                            data = json.load(f)
                        profile_name = data.get('profile_name', 'Unknown')
                        saved_date = data.get('saved_date', 'Unknown date')
                        display_text = f"{profile_name} ({saved_date})"
                    except:
                        # If can't load the profile info, just use filename
                        display_text = file.replace('_preferences.json', '')
                    
                    listbox.insert(i, display_text)
                    
                # Select the first item by default
                listbox.selection_set(0)
                
                # Variable to store the selected index
                selected_index = [0]  # Using a list to make it mutable for the inner function
                
                def on_select():
                    selected_index[0] = listbox.curselection()[0]
                    profile_window.destroy()
                    
                def on_cancel():
                    selected_index[0] = -1
                    profile_window.destroy()
                    
                # Buttons
                button_frame = ttk.Frame(frame)
                button_frame.pack(fill=tk.X, pady=10)
                
                ttk.Button(button_frame, text="Load Selected", command=on_select).pack(side=tk.LEFT, padx=5, expand=True)
                ttk.Button(button_frame, text="Cancel", command=on_cancel).pack(side=tk.RIGHT, padx=5, expand=True)
                
                # Wait for the window to be closed
                self.root.wait_window(profile_window)
                
                # If the user cancelled, return
                if selected_index[0] == -1:
                    return
                    
                # Get the selected file
                file_to_load = os.path.join(self.config_dir, prefs_files[selected_index[0]])
            
            # Load the preferences from the selected file
            with open(file_to_load, 'r') as f:
                prefs = json.load(f)
                
            # Apply loaded preferences using helper method
            self._apply_preferences(prefs)
            
            # Get profile name for message
            profile_name = prefs.get('profile_name', os.path.basename(file_to_load).replace('_preferences.json', ''))
            
            # Show success message with details about what was loaded
            msg = f"Profile '{profile_name}' loaded:\n\n"
            msg += f"• Language: {self.selected_lang.get()}\n"
            msg += f"• Debug mode: {'Enabled' if self.debug_enabled.get() else 'Disabled'}\n"
            
            if hasattr(self, '_text_similarity_threshold'):
                msg += f"• Text similarity threshold: {self._text_similarity_threshold}\n"
            
            if 'saved_date' in prefs:
                msg += f"\nSaved on: {prefs['saved_date']}"
                
            messagebox.showinfo("Settings Loaded", msg)
            
        except Exception as e:
            # Show error message
            messagebox.showerror(
                "Error Loading Settings", 
                f"Failed to load preferences: {str(e)}"
            )
            import traceback
            traceback.print_exc()
        
    def load_preferences(self):
        """Load preferences from file"""
        try:
            # First try to load from config directory
            prefs_file = os.path.join(self.config_dir, 'default_preferences.json')
            
            # If file doesn't exist in config_dir, check in capture_dir (for backward compatibility)
            if not os.path.exists(prefs_file):
                old_prefs_file = os.path.join(self.capture_dir, 'default_preferences.json') 
                if os.path.exists(old_prefs_file):
                    print(f"Found preferences in old location: {old_prefs_file}")
                    prefs_file = old_prefs_file
                else:
                    print(f"No preference file found at {prefs_file} or {old_prefs_file}")
                    return
            
            # Load and parse the JSON file
            print(f"Attempting to load preferences from: {prefs_file}")
            with open(prefs_file, 'r') as f:
                prefs = json.load(f)
            
            print(f"Loaded preferences: {prefs}")
            
            # Apply loaded preferences using helper method
            self._apply_preferences(prefs)
                    
            print(f"Preferences successfully loaded from: {prefs_file}")
        except Exception as e:
            print(f"Error loading preferences: {str(e)}")
            import traceback
            traceback.print_exc()  # This will print the full error with line numbers

    def log_debug(self, message):
        if self.debug_enabled.get():
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            log_path = os.path.join(self.capture_dir, "ocr_debug.log")
            with open(log_path, "a", encoding='utf-8') as f:
                f.write(f"{timestamp}: {message}\n")
                f.flush()

    def log_with_flush(self, message):
        """Log a message and immediately flush the output"""
        print(message, flush=True)
        if hasattr(self, 'log_debug') and self.debug_enabled.get():
            self.log_debug(message)
        
    def get_lang_code(self):
        selected = self.selected_lang.get()
        return next(lang[1] for lang in self.languages if lang[0] == selected)

    def detect_dpi_scaling(self):
        """More robust method to detect screen DPI scaling"""
        try:
            print("Detecting DPI scaling...")
            
            # Method 1: Use ctypes on Windows
            try:
                import ctypes
                user32 = ctypes.windll.user32
                
                # Try to get DPI awareness first
                awareness = ctypes.c_int()
                error = ctypes.windll.shcore.GetProcessDpiAwareness(0, ctypes.byref(awareness))
                
                if error == 0:  # S_OK
                    # Now get the actual scale factor
                    scale_factor = ctypes.windll.shcore.GetScaleFactorForDevice(0) / 100
                    print(f"Method 1: DPI scaling detected: {scale_factor}")
                    return scale_factor
            except Exception as e:
                print(f"Method 1 failed: {str(e)}")
            
            # Method 2: Use Tkinter's scaling
            try:
                # Get Tkinter's scaling factor
                scale_factor = self.root.tk.call('tk', 'scaling')
                print(f"Method 2: Tkinter scaling: {scale_factor}")
                # Tkinter scaling is typically 96 DPI = 1.0
                # Convert to Windows scaling (where 96 DPI = 1.0, 120 DPI = 1.25, 144 DPI = 1.5)
                return scale_factor
            except Exception as e:
                print(f"Method 2 failed: {str(e)}")
            
            # Method 3: Use winfo_fpixels
            try:
                # Get the ratio of pixels per point
                scale_factor = self.root.winfo_fpixels('1i') / 96.0
                print(f"Method 3: winfo_fpixels scaling: {scale_factor}")
                return scale_factor
            except Exception as e:
                print(f"Method 3 failed: {str(e)}")
                
            # If all methods fail, return a default value of 1.0
            print("All methods failed, using default scaling of 1.0")
            return 1.0
            
        except Exception as e:
            print(f"Critical error in detect_dpi_scaling: {str(e)}")
            return 1.0  # Default to no scaling
        
    def create_selection_window(self):
        """Create a fullscreen window for selecting an area to capture"""
        try:
            print("Creating full-screen selection window")
            print(f"Using scaling factor: {self.scale_factor}")
            
            # Clean up any previous state
            self.reset_selection_state()
            # IMPROVED: Force garbage collection to clean up old windows
            import gc
            gc.collect()
            
            # IMPROVED: More thorough cleanup of any previous selection window
            if hasattr(self, 'selection_window') and self.selection_window is not None:
                print("WARNING: Selection window already exists, destroying old window")
                try:
                    try:
                        if self.selection_window.winfo_exists():
                            for widget in self.selection_window.winfo_children():
                                widget.destroy()
                            self.selection_window.destroy()
                            print("Old selection window destroyed")
                    except Exception as e:
                        print(f"Error checking/destroying existing selection window: {str(e)}")
                except Exception as e:
                    print(f"Error accessing selection window: {str(e)}")
                
                # Force reference removal
                self.selection_window = None
                
                # Additional cleanup to ensure the window is gone
                gc.collect()
                
            # IMPROVED: Explicitly create and reference all widgets            
            # Create a transparent window covering the entire screen
            self.selection_window = tk.Toplevel(self.root)
            
            # Debug info - check window properties
            print(f"Selection window created with ID: {self.selection_window}")
            
            # Set window attributes
            self.selection_window.attributes('-fullscreen', True)
            self.selection_window.attributes('-alpha', 0.5)  # Increased visibility
            self.selection_window.attributes('-topmost', True)
            
            # Remove window decorations
            self.selection_window.overrideredirect(True)
            
            # Configure background color
            self.selection_window.configure(bg='black')
            
            # Create a canvas to draw the selection rectangle
            self.canvas = tk.Canvas(self.selection_window, 
                                    highlightthickness=0, 
                                    bg='black', 
                                    cursor='cross')
            self.canvas.pack(fill=tk.BOTH, expand=True)
            
            # Get actual screen dimensions
            screen_width = self.root.winfo_screenwidth()
            screen_height = self.root.winfo_screenheight()
            self.canvas.config(width=screen_width, height=screen_height)
            
            # Debug info
            print(f"Canvas created with dimensions: {screen_width}x{screen_height}")
            
            # Bind mouse events
            self.canvas.bind('<ButtonPress-1>', self.start_selection)
            self.canvas.bind('<B1-Motion>', self.update_selection)
            self.canvas.bind('<ButtonRelease-1>', self.end_selection)
            
            # Add instruction text
            instruction_text = """
            Click and drag to select capture area.
            Press ESC to cancel.
            Press Enter to confirm selection.
            """
            self.instruction_label = tk.Label(
                self.selection_window, 
                text=instruction_text, 
                bg='yellow', 
                font=('Arial', 12),
                justify=tk.CENTER
            )
            self.instruction_label.place(relx=0.5, rely=0.95, anchor=tk.S)
            
            # IMPROVED: Store references to all event bindings so we can explicitly unbind them
            self.selection_bindings = []
            binding1 = self.selection_window.bind('<Return>', self.confirm_selection)
            binding2 = self.selection_window.bind('<Escape>', self.cancel_selection)
            self.selection_bindings.extend([binding1, binding2])
            
            # IMPROVED: Add protocol handler for window close event
            self.selection_window.protocol("WM_DELETE_WINDOW", self.cancel_selection)
            
            # Force window to be on top and grab focus
            self.selection_window.lift()
            self.selection_window.focus_force()
            
            # Give a moment for the window to display
            self.selection_window.update()
            
            print("Selection window created successfully")
        
        except Exception as e:
            print(f"Error creating selection window: {str(e)}")
            self.log_debug(f"Error creating selection window: {str(e)}")
            self.status_var.set(f"Selection window error: {str(e)}")

            # IMPROVED: More thorough cleanup on error
            if hasattr(self, 'selection_window') and self.selection_window is not None:
                try:
                    self.selection_window.destroy()
                except Exception as cleanup_err:
                    print(f"Error cleaning up window after creation error: {str(cleanup_err)}")
                finally:
                    self.selection_window = None
            
            if hasattr(self, 'canvas') and self.canvas is not None:
                self.canvas = None
            # Re-enable start button on error
            self.start_button['state'] = tk.NORMAL
            
            # Ensure the error is propagated
            raise

    def start_selection(self, event):
        self.log_with_flush(f"Selection started at: Canvas ({event.x}, {event.y}), Root ({event.x_root}, {event.y_root})")
        print(f"Selection started at: Canvas ({event.x}, {event.y}), Root ({event.x_root}, {event.y_root})")
        
        # Clear any existing rectangle from previous selection attempts
        if hasattr(self, 'rect') and self.rect is not None:
            self.canvas.delete(self.rect)
            self.rect = None
        
        # Clear all items on the canvas to ensure no leftover selections
        self.canvas.delete("selection")  # Delete all objects with "selection" tag
        
        # Start of selection
        self.start_x = event.x
        self.start_y = event.y
        
        # Create initial rectangle with a tag
        self.rect = self.canvas.create_rectangle(
            self.start_x, self.start_y, self.start_x, self.start_y, 
            outline='red', width=2,
            tags=("selection",)
        )

    def update_selection(self, event):
        # Update rectangle as user drags
        if self.rect and self.start_x is not None and self.start_y is not None:
            # Remove the old rectangle and create a new one
            self.canvas.delete(self.rect)
            
            # Create new rectangle with current mouse position
            self.rect = self.canvas.create_rectangle(
                self.start_x, self.start_y, event.x, event.y, 
                outline='red', width=2, fill='red', stipple='gray50',
                tags=("selection",)
            )

    def end_selection(self, event):
        print(f"Selection ended at: Canvas ({event.x}, {event.y}), Root ({event.x_root}, {event.y_root})")
        # Final rectangle placement
        if self.rect and self.start_x is not None and self.start_y is not None:
            # Ensure the rectangle is created properly even if dragged in any direction
            x1, y1 = min(self.start_x, event.x), min(self.start_y, event.y)
            x2, y2 = max(self.start_x, event.x), max(self.start_y, event.y)
            
            # Delete existing rectangle and redraw with correct coordinates
            self.canvas.delete(self.rect)
            self.rect = self.canvas.create_rectangle(
                x1, y1, x2, y2, 
                outline='green', width=3, fill='green', stipple='gray50',
                tags=("selection",)
            )
            
            # Store the selection coordinates
            self.selection_coords = (x1, y1, x2, y2)
            print(f"Selection coordinates: {self.selection_coords}")

    def confirm_selection(self, event=None):
        # Confirm the selected area
        try:
            print("Confirming selection")
            if hasattr(self, 'selection_coords') and self.selection_coords:
                # Raw unscaled coordinates
                x1, y1, x2, y2 = self.selection_coords
                
                # Debug print raw coordinates
                print(f"Raw selection coordinates: {x1}, {y1}, {x2}, {y2}")
                print(f"Scaling factor: {self.scale_factor}")
                
                # FIXED: For screen capture, we need to account for DPI scaling correctly
                # When scale factor is higher than 1, we're seeing smaller coordinates on screen
                # than what we need to capture, so we should multiply by the scale factor
                scaled_x1 = int(x1 * self.scale_factor)
                scaled_y1 = int(y1 * self.scale_factor)
                scaled_x2 = int(x2 * self.scale_factor)
                scaled_y2 = int(y2 * self.scale_factor)
                
                # Ensure minimum capture area
                width = scaled_x2 - scaled_x1
                height = scaled_y2 - scaled_y1
                
                # Validate capture area
                if width < 50 or height < 50:
                    messagebox.showwarning("Invalid Selection", 
                        "Selected area is too small. Please select a larger area.")
                    return
                
                # Store the scaled coordinates
                self.capture_area = (scaled_x1, scaled_y1, scaled_x2, scaled_y2)
                
                print("Selection confirmed:")
                print(f"Raw coordinates: {self.selection_coords}")
                print(f"Scaled coordinates: {self.capture_area}")
                print(f"Selection size: {width}x{height}")
                
                # Destroy selection window
                self.destroy_window('selection_window')
                
                # Start OCR
                self.start_ocr()
                
                # Update status
                self.status_var.set("Area selected. Starting capture...")
            else:
                print("No selection coordinates found")
                messagebox.showwarning("Warning", "Please select an area first")
            
            sys.stdout.flush()
                    
        except Exception as e:
            print(f"Error confirming selection: {str(e)}")
            messagebox.showerror("Error", f"Failed to confirm selection: {str(e)}")

    def reset_selection_state(self):
        """Reset all selection-related variables to ensure a clean state"""
        print("Resetting selection state")
        
        # Reset selection variables
        self.start_x = None
        self.start_y = None
        self.rect = None
        self.selection_coords = None
        self.debug_capture_saved = False
        
        # Reset capture variables
        self.capture_stop_flag = False
        
        # Use the unified method to destroy windows
        self.destroy_window('selection_window')
        
        # Clean up canvas and other references
        self.canvas = None
        self.instruction_label = None
        self.selection_bindings = []
        
        # Force garbage collection to clean up unreferenced windows
        import gc
        gc.collect()
        
    def cancel_selection(self, event=None):
        """Cancel the selection process"""
        try:
            print("Cancelling selection")
            
            # Use the unified method to destroy the window
            self.destroy_window('selection_window')
            
            # Clean up canvas and label references
            self.canvas = None
            self.instruction_label = None
            
            # Re-enable start button
            self.start_button['state'] = tk.NORMAL
            self.status_var.set("Selection cancelled")
        except Exception as e:
            print(f"Error cancelling selection: {str(e)}")
            # Ensure button is re-enabled even on error
            try:
                self.start_button['state'] = tk.NORMAL
            except Exception as btn_err:
                print(f"Error re-enabling button: {str(btn_err)}")
            
    def text_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity ratio between two texts"""
        return difflib.SequenceMatcher(None, text1, text2).ratio()
        
    # Cache processed sentences to avoid re-processing
    def extract_sentences(self, text):
        if not text:
            return []
        
        # Use a more efficient regex compilation
        if not hasattr(self, '_sentence_regex'):
            self._sentence_regex = re.compile(r'[.!?]+')
        
        # Split by compiled regex
        sentences = []
        for part in self._sentence_regex.split(text):
            part = part.strip()
            if part:
                sentences.append(part)
        return sentences

    def do_drag_capture(self, event):
        """Move the capture window during drag"""
        try:
            if self.drag_start_x is not None and self.drag_start_y is not None:
                # Calculate the window's new position
                x = self.capture_window.winfo_x() + (event.x - self.drag_start_x)
                y = self.capture_window.winfo_y() + (event.y - self.drag_start_y)
                
                # Move the window
                self.capture_window.geometry(f"+{x}+{y}")
                
        except Exception as e:
            print(f"Error during capture window drag: {str(e)}")

    def end_drag_capture(self, event):
        """End dragging the capture window"""
        try:
            # FIXED: More robust checks for capture_window
            if not hasattr(self, 'capture_window') or self.capture_window is None:
                print("Capture window is None, cannot end drag")
                return
                
            # FIXED: Safer way to check if window exists
            window_exists = False
            try:
                window_exists = self.capture_window.winfo_exists()
                                                                             
                          
            except Exception as e:
                print(f"Error checking if capture window exists: {str(e)}")
                self.capture_window = None  # Reset to None on error
                return
                
            if not window_exists:
                print("Capture window no longer exists, cannot end drag")
                self.capture_window = None  # Reset to None
                return
                
            # Get the current window position
            current_x = self.capture_window.winfo_x()
            current_y = self.capture_window.winfo_y()
            current_width = self.capture_window.winfo_width()
            current_height = self.capture_window.winfo_height()
            
            # Convert screen coordinates back to absolute coordinates for capture
            abs_x1 = int(current_x * self.scale_factor)
            abs_y1 = int(current_y * self.scale_factor)
            abs_x2 = abs_x1 + int(current_width * self.scale_factor)
            abs_y2 = abs_y1 + int(current_height * self.scale_factor)
            
            # Update the capture area
            self.capture_area = (abs_x1, abs_y1, abs_x2, abs_y2)
            
            print(f"Drag ended. New capture area: {self.capture_area}")
            
            # Reset drag start coordinates
            self.drag_start_x = None
            self.drag_start_y = None
            
        except Exception as e:
            print(f"Error ending capture window drag: {str(e)}")
            # Ensure we clean up on error
            self.drag_start_x = None
            self.drag_start_y = None

    def has_significant_new_content(self, new_text, previous_text, threshold=None):
        # Enhanced method to filter out OCR noise and partial captures
        # Use stored threshold if available and none is provided
        if threshold is None and hasattr(self, '_text_similarity_threshold'):
            threshold = self._text_similarity_threshold
        elif threshold is None:
            threshold = 0.8  # Default value

        # Remove very short fragments and pure noise
        if len(new_text) < 10:
            return False
        
        # Remove common OCR noise patterns
        new_text = re.sub(r'\b[a-zA-Z]{1,2}\b', '', new_text)
        new_text = re.sub(r'\s+', ' ', new_text).strip()
        
        # If text is still too short after cleaning, reject
        if len(new_text) < 10:
            return False
        
        # If no previous text, always accept
        if not previous_text:
            return True
        
        # Check similarity, but with a lower threshold
        similarity = self.text_similarity(new_text, previous_text)
        
        # More strict comparison
        return similarity < threshold

    def clean_ocr_text(self, text):
        """
        Clean OCR text to remove noise and improve readability
        """
        # Remove single letters and very short fragments
        text = re.sub(r'\b[a-zA-Z]{1,2}\b', '', text)
        
        # Remove weird Unicode or special characters
        text = re.sub(r'[^\w\s.,!?():\-]', '', text)
        
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text
    
    def capture_screen(self):
        """Capture screen content and perform OCR, with thread-safe UI handling"""
        try:
            # Verify capture area is set
            if not hasattr(self, 'capture_area') or self.capture_area is None:
                # Using after() to show error on main thread
                self.root.after(0, lambda: messagebox.showerror("Error", "No capture area selected"))
                return
            
            x1, y1, x2, y2 = self.capture_area
            print(f"Capturing area: {x1}, {y1}, {x2}, {y2}")
            
            # Thread-safe way to create UI elements
            def create_capture_window():
                # Create a small, semi-transparent yellow window to show capture area
                self.capture_window = tk.Toplevel(self.root)
                self.capture_window.overrideredirect(True)
                self.capture_window.attributes('-topmost', True)
                self.capture_window.attributes('-alpha', 0.3)
                self.capture_window.configure(bg='yellow')
                
                # Position and size the capture window - adjust for DPI scaling
                width = x2 - x1
                height = y2 - y1
                
                # Convert from scaled to screen coordinates
                screen_x1 = int(x1 / self.scale_factor)
                screen_y1 = int(y1 / self.scale_factor)
                screen_width = int(width / self.scale_factor)
                screen_height = int(height / self.scale_factor)
                
                self.capture_window.geometry(f"{screen_width}x{screen_height}+{screen_x1}+{screen_y1}")
                
                # Create control frame
                control_frame = tk.Frame(self.capture_window, bg='blue')
                control_frame.pack(fill=tk.X, side=tk.TOP, pady=0)
                
                # Status label
                self.status_label = tk.Label(control_frame, text="Capturing... (Click and drag to move)", 
                                       bg='blue', fg='white', font=('Arial', 10))
                self.status_label.pack(side=tk.LEFT, padx=10)
                
                # STOP button
                stop_button = tk.Button(control_frame, text="STOP", 
                                       command=self.stop_capture,
                                       bg='red', fg='white',
                                       font=('Arial', 10, 'bold'))
                stop_button.pack(side=tk.RIGHT, padx=10)
                
                # Bind mouse events for dragging
                self.capture_window.bind('<Button-1>', self.start_drag_capture)
                self.capture_window.bind('<B1-Motion>', self.do_drag_capture)
                self.capture_window.bind('<ButtonRelease-1>', self.end_drag_capture)
                
                # Store window in a global to prevent garbage collection
                self.root.capture_window_ref = self.capture_window
                
                return True
            
            # Create window on the main thread
            window_created = [False]  # Use a list to make it mutable from inside the lambda
            self.root.after(0, lambda: window_created.__setitem__(0, create_capture_window()))
            
            # Wait for window to be created
            timeout = 10  # Wait up to 1 second
            while not window_created[0] and timeout > 0:
                time.sleep(0.1)
                timeout -= 1
            
            if timeout <= 0:
                print("Timeout waiting for window creation")
                return
                
            # Variables for dragging
            self.drag_start_x = None
            self.drag_start_y = None
            
            # Adjust capture area to exclude control frame
            adjusted_y1 = y1 + int(25 * self.scale_factor)  # Adjust for control frame height
            adjusted_capture_area = (x1, adjusted_y1, x2, y2)
            
            print("Starting capture process")
            # Update status with thread lock
            with self.thread_lock:
                # Thread-safe update of UI
                self.root.after(0, lambda: self.status_var.set("Capturing... (Press Ctrl+Q or STOP to stop)"))
                self.running = True
                self.capture_stop_flag = False
            
            last_text = ""
            # Create output file
            timestamp = datetime.now().strftime('%Y-%m-%d-%H-%M-%S')
            self.current_capture_timestamp = timestamp
            filename = f"capture_{timestamp}.txt"
            output_file = os.path.join(self.capture_dir, filename)
            
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(f"Caption capture started: {datetime.now()}\n\n")
            
            # Track consecutive similar captures to adapt interval
            similar_captures_count = 0
            capture_interval = 3  # Start with 3 seconds interval
            
            # Create collection for text history
            text_history = deque(maxlen=5)  # Keep only last 5 texts
            
            # Flag to track window destruction
            window_destroyed = False
            
            # Start key checking thread
            def check_stop_key():
                while True:
                    # Check if should continue
                    if self.stop_event.is_set():
                        break
                    
                    # Check for stop key
                    if keyboard.is_pressed('ctrl+q'):
                        print("Ctrl+Q pressed, stopping capture")
                        with self.thread_lock:
                            self.capture_stop_flag = True
                        break
                    
                    time.sleep(0.1)  # Small sleep to avoid CPU hogging
            
            stop_thread = threading.Thread(target=check_stop_key, daemon=True)
            stop_thread.start()
            
            # Main capture loop
            while True:
                try:
                    # Check window_destroyed flag first
                    if window_destroyed:
                        print("Window already destroyed, stopping capture loop")
                        break
                    
                    # Check if should continue with thread lock
                    with self.thread_lock:
                        if self.capture_stop_flag:
                            break
                    
                    # Thread-safe way to check if window exists
                    window_exists = [False]
                    
                    def check_window_exists():
                        if hasattr(self, 'capture_window') and self.capture_window is not None:
                            try:
                                exists = self.capture_window.winfo_exists()
                                window_exists[0] = exists
                                return exists
                            except Exception as e:
                                print(f"Error checking window existence: {str(e)}")
                                return False
                        return False
                    
                    # Execute check on main thread
                    self.root.after(0, check_window_exists)
                    
                    # Wait a short time for the check to complete
                    time.sleep(0.1)
                    
                    if not window_exists[0]:
                        print("Capture window no longer exists, stopping capture loop")
                        self.capture_window = None
                        break
                    
                    # Thread-safe way to get window position
                    window_info = [None, None, None, None]  # x, y, width, height
                    
                    def get_window_position():
                        if hasattr(self, 'capture_window') and self.capture_window is not None:
                            try:
                                window_info[0] = self.capture_window.winfo_x()
                                window_info[1] = self.capture_window.winfo_y()
                                window_info[2] = self.capture_window.winfo_width()
                                window_info[3] = self.capture_window.winfo_height()
                            except Exception as e:
                                print(f"Error getting window position: {str(e)}")
                    
                    # Execute position check on main thread
                    self.root.after(0, get_window_position)
                    
                    # Wait a short time for the check to complete
                    time.sleep(0.1)
                    
                    # If we couldn't get window info, skip this iteration
                    if None in window_info:
                        print("Could not get window position, skipping capture")
                        time.sleep(1)
                        continue
                    
                    current_x, current_y, current_width, current_height = window_info
                    
                    # Convert screen coordinates to absolute coordinates
                    abs_x1 = int(current_x * self.scale_factor)
                    abs_y1 = int(current_y * self.scale_factor)
                    abs_x2 = abs_x1 + int(current_width * self.scale_factor)
                    abs_y2 = abs_y1 + int(current_height * self.scale_factor)
                    
                    # Adjust for control frame height
                    adjusted_y1 = abs_y1 + int(25 * self.scale_factor)
                    current_capture_area = (abs_x1, adjusted_y1, abs_x2, abs_y2)
                    
                    # Take screenshot with updated area
                    screenshot = ImageGrab.grab(bbox=current_capture_area)
                    
                    # Check if we should resize for performance (large images)
                    img_width, img_height = screenshot.size
                    if img_width * img_height > 1000000:  # More than 1 megapixel
                        scale = 0.7  # Scale down to 70%
                        screenshot = screenshot.resize(
                            (int(img_width * scale), int(img_height * scale)),
                            resample=Image.LANCZOS
                        )
                    
                    # Perform OCR
                    raw_text = pytesseract.image_to_string(
                        screenshot, 
                        lang=self.get_lang_code(),
                        config=self.get_ocr_config()  # Best Live Caption configuration
                    ).strip()
                    
                    # Release screenshot to free memory
                    del screenshot
                    
                    # Clean the OCR text
                    text = self.clean_ocr_text(raw_text)
                    
                    # Check if text has significant new content
                    if text and self.has_significant_new_content(text, last_text):
                        # Add to history
                        text_history.append(text)
                        
                        # Save to file with timestamp
                        with open(output_file, 'a', encoding='utf-8') as f:
                            f.write(f"[{datetime.now().strftime('%H:%M:%S')}] {text}\n")
                        
                        # Update last text
                        last_text = text
                        
                        # Thread-safe update of UI text
                        if len(text) > 90:
                            first_line = text[:30]
                            second_line = text[30:60]
                            third_line = text[60:90]
                            status_text = f"Last capture:\n{first_line}\n{second_line}\n{third_line}..."
                        else:
                            first_line = text[:min(30, len(text))]
                            second_line = text[30:min(60, len(text))]
                            third_line = text[60:min(90, len(text))]
                            status_text = f"Last capture:\n{first_line}\n{second_line}\n{third_line}"
                        self.root.after(0, lambda: self.status_var.set(status_text))
                        
                        # Thread-safe update of label
                        def update_label():
                            if (hasattr(self, 'capture_window') and 
                                hasattr(self, 'status_label') and
                                self.capture_window is not None and 
                                self.status_label is not None):
                                try:
                                    if self.capture_window.winfo_exists():
                                        self.status_label.config(text=f"Last: {text[:20]}...")
                                except Exception as e:
                                    print(f"Error updating status label: {str(e)}")
                                    
                        # Execute label update on main thread
                        self.root.after(0, update_label)
                        
                        # Reset counters for successful capture
                        similar_captures_count = 0
                        if capture_interval > 3:
                            capture_interval = 3
                    else:
                        # If no significant new content, adjust interval
                        similar_captures_count += 1
                        if similar_captures_count > 3:
                            # Increase interval to reduce processing load
                            capture_interval = min(capture_interval + 1, 5)  # Max 5 seconds
                    
                    # Dynamic sleep based on capture interval
                    time.sleep(capture_interval)
                        
                except Exception as e:
                    print(f"Error during capture iteration: {str(e)}")
                    self.log_debug(f"Capture error: {str(e)}")
                    time.sleep(1)  # Sleep on error to avoid rapid error loops
            
            print("Exited capture loop")
            
            # Thread-safe cleanup of capture window
            def destroy_capture_window():
                if hasattr(self, 'capture_window') and self.capture_window is not None:
                    try:
                        if self.capture_window.winfo_exists():
                            self.capture_window.destroy()
                            print("Capture window destroyed in cleanup")
                        else:
                            print("Capture window no longer exists in cleanup")
                    except Exception as e:
                        print(f"Error cleaning up capture window: {str(e)}")
                    finally:
                        # Set to None regardless of what happened
                        self.capture_window = None
                        # Remove reference to prevent memory leaks
                        if hasattr(self.root, 'capture_window_ref'):
                            delattr(self.root, 'capture_window_ref')
            
            # Execute window destruction on main thread
            self.root.after(0, destroy_capture_window)
            
            # Wait for window to be destroyed
            time.sleep(0.2)
            
            print("Capture thread completed")
                
        except Exception as e:
            # More detailed error logging
            import traceback
            print(f"Critical error in capture_screen: {str(e)}")
            print("Error traceback:")
            traceback.print_exc()
            
            # Thread-safe cleanup and error reporting
            def handle_critical_error():
                # Set capture_window to None
                if hasattr(self, 'capture_window'):
                    try:
                        if self.capture_window is not None and self.capture_window.winfo_exists():
                            self.capture_window.destroy()
                    except:
                        pass
                    self.capture_window = None
                    
                # Update status with error
                self.status_var.set(f"Error: {str(e)}")
                
            # Execute error handling on main thread
            self.root.after(0, handle_critical_error)

    def start_capture(self):
        try:
            print("Starting capture process")
            self.status_var.set("Select area and press OK or Enter")
            self.reset_selection_state()  # Reset any previous selection state
            self.create_selection_window()
            self.start_button['state'] = tk.DISABLED        
        except Exception as e:
            print(f"Error in start_capture: {str(e)}")
            messagebox.showerror("Error", f"Failed to start capture: {str(e)}")
            self.start_button['state'] = tk.NORMAL  # Re-enable the button on error
        
    def start_ocr(self):
        """Start the OCR process after area selection"""
        try:
            print("========== STARTING OCR CAPTURE ==========")
            
            print(f"OCR s=Started at {datetime.now()}")
            
            # Verify we have a selected area
            if not hasattr(self, 'capture_area') or not self.capture_area:
                print("Cannot start OCR: No capture area selected")
                messagebox.showerror("Error", "No capture area selected. Please select an area first.")
                return
                
            # Set the running flag
            with self.thread_lock:
                self.running = True
            
            # Make sure selection window is closed to avoid interference
            if hasattr(self, 'selection_window') and self.selection_window:
                try:
                    print("Closing selection window before starting OCR")
                    self.selection_window.destroy()
                except Exception as e:
                    print(f"Error closing selection window: {str(e)}")
                finally:
                    self.selection_window = None
            
            # Start the capture in a new thread
            self.capture_thread = threading.Thread(target=self.capture_screen, daemon=True)
            self.capture_thread.start()
            
            print("OCR process started successfully")
            
        except Exception as e:
            print(f"Error in start_ocr: {str(e)}")
            self.log_debug(f"Error in start_ocr: {str(e)}")
            messagebox.showerror("Error", f"Failed to start OCR: {str(e)}")
            
            # Reset running flag on error
            self.running = False
            
            # Re-enable start button on error
            self.start_button['state'] = tk.NORMAL

    def start_drag_capture(self, event):
        """Start dragging the capture window"""
        print(f"Drag started at: ({event.x}, {event.y})")
        self.drag_start_x = event.x
        self.drag_start_y = event.y
    
    def prompt_for_filename(self):
        """Ask user for a name to include in the processed filename"""
        try:
            filename = simpledialog.askstring("Save As", "Enter a name for the captured file:",
                                              parent=self.root)
            if filename:
                # Remove spaces and special characters
                filename = re.sub(r'[^\w\-]', '_', filename)
                return filename
            return None
        except Exception as e:
            print(f"Error prompting for filename: {str(e)}")
            return None

    def stop_capture(self):
        """Stop the capture process and clean up all resources with thread-safe UI handling"""
        try:
            # If we're already in the process of stopping, don't do it again
            if hasattr(self, '_stopping') and self._stopping:
                print("Stop capture already in progress, skipping redundant call")
                return
            
            # Set flag to prevent multiple stop operations
            self._stopping = True
            
            print("========== STOP OCR CAPTURE ==========")
            
            print(f"OCR Stopped at {datetime.now()}")
            
            # Set all stop flags
            with self.thread_lock:
                self.capture_stop_flag = True
                self.running = False
                self.stop_event.set()
            
            # Thread-safe capture window handling
            def destroy_capture_window():
                self.destroy_window('capture_window')
            
            # Execute window destruction on main thread
            self.root.after(0, destroy_capture_window)
            
            # Add a small delay to allow window destruction to complete
            time.sleep(0.3)
            
            # Improved capture thread handling - single check and join
            capture_thread = self.capture_thread  # Get local reference to avoid race conditions
            if capture_thread is not None and capture_thread.is_alive():
                print("Joining capture thread...")
                try:
                    # Single join with adequate timeout
                    capture_thread.join(timeout=1.5)
                    if capture_thread.is_alive():
                        print("WARNING: Capture thread did not terminate within timeout")
                    else:
                        print("Capture thread terminated successfully")
                except Exception as e:
                    print(f"Error joining capture thread: {str(e)}")
            
            # Clear the reference regardless of success
            self.capture_thread = None
            
            # Reset all selection and capture variables
            self.selection_coords = None
            self.capture_area = None
            self.rect = None
            self.start_x = None
            self.start_y = None
            self.drag_start_x = None
            self.drag_start_y = None
            self.debug_capture_saved = False
            
            # Process files in a thread-safe way
            def process_files():
                # Only process files if this is a real stop (not just cleanup)
                # and we have a current timestamp (meaning we've been capturing)
                if hasattr(self, 'current_capture_timestamp') and self.current_capture_timestamp:
                    # Process the latest capture file if needed
                    latest_file = self.find_latest_capture_file()
                    print(f"Latest capture file found: {latest_file}")
                    if latest_file and (not hasattr(self, 'last_processed_file') or self.last_processed_file != latest_file):
                        print(f"Processing file: {latest_file}")
                        # Ask user for a name
                        custom_name = self.prompt_for_filename()
                        print(f"User provided name: {custom_name if custom_name else '(none/canceled)'}")
                        
                        # Process the file
                        processed_file = self.post_process_capture_file(latest_file, custom_name)

                        if processed_file:
                            self.last_processed_file = latest_file
                            print(f"File processing complete. Result saved to: {processed_file}")
                        
                        if custom_name:
                            self.status_var.set(f"Capture stopped and saved with name: {custom_name}")
                        else:
                            self.status_var.set("Capture stopped and processed with default name")
                            
                        # Reset timestamp to prevent processing again
                        self.current_capture_timestamp = None
                    else:
                        print(f"No new file to process. Latest: {latest_file}, Last processed: {getattr(self, 'last_processed_file', None)}")
                        self.status_var.set("Capture stopped (no new file to process)")
                else:
                    print(f"No capture in progress (timestamp: {getattr(self, 'current_capture_timestamp', None)}), skipping file processing")
                    self.status_var.set("Ready")
                
                # Re-enable the start button
                self.start_button['state'] = tk.NORMAL
            
            # Execute file processing on main thread
            self.root.after(0, process_files)
            
            print("Capture process stopped successfully")
            
        except Exception as e:
            print(f"Critical error in stop_capture: {str(e)}")
            # More detailed error logging
            import traceback
            traceback.print_exc()
            
            self.log_debug(f"Critical error in stop_capture: {str(e)}")
            
            # Thread-safe error recovery
            def handle_error():
                # Ensure button is re-enabled
                try:
                    self.start_button['state'] = tk.NORMAL
                except:
                    pass
                    
                # Set error status
                self.status_var.set(f"Error stopping capture: {str(e)}")
                
                # Clean up windows
                if hasattr(self, 'capture_window') and self.capture_window is not None:
                    try:
                        self.capture_window.destroy()
                    except:
                        pass
                    self.capture_window = None
                    
            # Execute error handling on main thread
            self.root.after(0, handle_error)
        finally:
            # Reset the event for next use
            self.stop_event.clear()
            self._stopping = False

    def run(self):
        """Start the application's main event loop"""
        try:
            print("Starting main loop")
            # Set up protocol for the window close event
            self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
            # Start Tkinter's main event loop
            self.root.mainloop()
        except Exception as e:
            print(f"Error in run: {str(e)}")
            import traceback
            traceback.print_exc()

    def on_closing(self):
        """Handle application shutdown"""
        try:
            print("========== APPLICATION CLOSING ==========")
            
            # Save preferences if that method exists
            if hasattr(self, 'save_preferences'):
                try:
                    self.save_preferences()
                    print("Preferences saved")
                except Exception as pref_err:
                    print(f"Error saving preferences: {str(pref_err)}")
            
            # Stop any active capture process
            try:
                if hasattr(self, 'stop_capture'):
                    self.stop_capture()
            except Exception as stop_err:
                print(f"Error stopping capture: {str(stop_err)}")
            
            # Ensure all windows are destroyed
            windows_to_check = ['selection_window', 'capture_window']
            for window_name in windows_to_check:
                self.destroy_window(window_name)
            
            # Force garbage collection before exiting
            import gc
            gc.collect()
            
            # Final goodbye message
            print(f"Application closed at at {datetime.now()}")
            print(f"Files saved in: {self.capture_dir}")
            # Clean up logging before exit
            if hasattr(self, 'cleanup_logging'):
                self.cleanup_logging()
            
            # Destroy the main window
            self.root.destroy()
            
        except Exception as e:
            print(f"Error during application closing: {str(e)}")
            import traceback
            traceback.print_exc()
            
            # Force exit in case of critical error
            try:
                self.root.destroy()
            except:
                pass

    def destroy_window(self, window_attr_name):
        """
        Unified method to safely destroy a window.
        
        Args:
            window_attr_name (str): The name of the window attribute to destroy
        
        Returns:
            bool: True if the window was successfully destroyed, False otherwise
        """
        try:
            # Check if the attribute exists and is not None
            if not hasattr(self, window_attr_name) or getattr(self, window_attr_name) is None:
                print(f"Window {window_attr_name} doesn't exist or is None, no action required")
                return False
                
            window = getattr(self, window_attr_name)
            
            # Check if the window still exists in the Tkinter system
            window_exists = False
            try:
                window_exists = window.winfo_exists()
            except Exception as e:
                print(f"Error checking if window {window_attr_name} exists: {str(e)}")
                
            if not window_exists:
                print(f"Window {window_attr_name} no longer exists in Tkinter system")
                setattr(self, window_attr_name, None)
                return False
                
            # Collect all bindings to remove
            bindings_attr_name = f"{window_attr_name}_bindings"
            if hasattr(self, bindings_attr_name) and getattr(self, bindings_attr_name):
                bindings = getattr(self, bindings_attr_name)
                for binding in bindings:
                    try:
                        window.unbind(binding)
                    except Exception as e:
                        print(f"Error unbinding event in {window_attr_name}: {str(e)}")
                # Clear the bindings list
                setattr(self, bindings_attr_name, [])
            
            # Unbind common events
            for event in ['<Button-1>', '<B1-Motion>', '<ButtonRelease-1>', '<Return>', '<Escape>']:
                try:
                    window.unbind(event)
                except Exception as e:
                    print(f"Error unbinding event {event} in {window_attr_name}: {str(e)}")
                    
            # Destroy all child widgets
            for widget in window.winfo_children():
                try:
                    widget.destroy()
                except Exception as e:
                    print(f"Error destroying child widget in {window_attr_name}: {str(e)}")
                    
            # Destroy the window
            try:
                window.destroy()
                print(f"Window {window_attr_name} was successfully destroyed")
            except Exception as e:
                print(f"Error destroying window {window_attr_name}: {str(e)}")
                
            # Set the attribute to None
            setattr(self, window_attr_name, None)
            
            # Force garbage collection
            import gc
            gc.collect()
            
            return True
        except Exception as e:
            print(f"Critical error during destruction of window {window_attr_name}: {str(e)}")
            # Still set the attribute to None for safety
            try:
                setattr(self, window_attr_name, None)
            except:
                pass
            return False
        
    def load_preferences(self):
        """Load preferences from file"""
        try:
            # First try to load from config directory
            prefs_file = os.path.join(self.config_dir, 'default_preferences.json')
            
            # If file doesn't exist in config_dir, check in capture_dir (for backward compatibility)
            if not os.path.exists(prefs_file):
                old_prefs_file = os.path.join(self.capture_dir, 'default_preferences.json') 
                if os.path.exists(old_prefs_file):
                    print(f"Found preferences in old location: {old_prefs_file}")
                    prefs_file = old_prefs_file
                else:
                    print(f"No preference file found at {prefs_file} or {old_prefs_file}")
                    return
            
            # Load and parse the JSON file
            print(f"Attempting to load preferences from: {prefs_file}")
            with open(prefs_file, 'r') as f:
                prefs = json.load(f)
            
            print(f"Loaded preferences: {prefs}")
                
            # Apply loaded preferences
            if 'language' in prefs:
                self.selected_lang.set(prefs['language'])
                print(f"Set language to: {prefs['language']}")
            
            if 'debug_enabled' in prefs:
                self.debug_enabled.set(prefs['debug_enabled'])
                print(f"Set debug mode to: {prefs['debug_enabled']}")
            
            if 'text_similarity_threshold' in prefs:
                # Store this value for use in has_significant_new_content
                self._text_similarity_threshold = prefs['text_similarity_threshold']
                print(f"Set text similarity threshold to: {prefs['text_similarity_threshold']}")
                    
            print(f"Preferences successfully loaded from: {prefs_file}")
        except Exception as e:
            print(f"Error loading preferences: {str(e)}")
            import traceback
            traceback.print_exc()  # This will print the full error with line numbers
            
    def find_latest_capture_file(self):
        """Find the most recent capture file in the capture directory, ignoring processed files"""
        try:
            # Only consider original capture files (not already processed ones)
            files = [f for f in os.listdir(self.capture_dir) 
                if f.startswith("capture_") 
                and f.endswith(".txt")
                and not "_processed" in f  # Skip already processed files
                and re.match(r'^capture_\d{4}-\d{2}-\d{2}-\d{2}-\d{2}-\d{2}\.txt$', f)]  # Match timestamp format
                    
            if not files:
                return None
                
            files.sort(reverse=True)  # Latest file first
            return os.path.join(self.capture_dir, files[0])
        except Exception as e:
            print(f"Error finding latest file: {str(e)}")
            return None

    def post_process_capture_file(self, filepath, custom_name=None):
        """Remove remaining duplications from the capture file and save with custom name if provided"""
        try:
            print(f"Post-processing capture file: {filepath}")
            
            with open(filepath, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                
            # Extract timestamp blocks
            blocks = []
            current_block = []
            timestamp_pattern = re.compile(r'^\[\d{2}:\d{2}:\d{2}\]')
            
            for line in lines:
                if timestamp_pattern.match(line):
                    if current_block:
                        blocks.append(current_block)
                    current_block = [line]
                elif current_block:
                    current_block.append(line)
                    
            if current_block:
                blocks.append(current_block)
            
            # Check if blocks list is empty before trying to access the first element
            if not blocks:
                print("No text blocks found in capture file.")
                # Create an empty block with header to avoid errors
                empty_block = [f"[{datetime.now().strftime('%H:%M:%S')}] No text was captured.\n"]
                blocks.append(empty_block)
                
            # Now it's safe to access blocks[0]
            unique_blocks = [blocks[0]]  # Keep the first block

            # Filter out blocks with duplicate content
            unique_blocks = [blocks[0]]  # Keep the first block
            
            for i in range(1, len(blocks)):
                current_text = ''.join(blocks[i])
                is_unique = True
                
                # Compare with previous blocks
                for prev_block in unique_blocks[-3:]:  # Check against last 3 unique blocks
                    prev_text = ''.join(prev_block)
                    # If similarity is too high, skip this block
                    if self.text_similarity(current_text, prev_text) > 0.75:
                        is_unique = False
                        break
                        
                if is_unique:
                    unique_blocks.append(blocks[i])
            
            # Use the timestamp from the original capture for the processed file
            timestamp = self.current_capture_timestamp
            if not timestamp:
                # Fallback: Extract timestamp from the filename
                base_filename = os.path.basename(filepath)
                timestamp_match = re.match(r'^capture_(\d{4}-\d{2}-\d{2}-\d{2}-\d{2}-\d{2})\.txt$', base_filename)
                if timestamp_match:
                    timestamp = timestamp_match.group(1)
                else:
                    # If all else fails, use current timestamp
                    timestamp = datetime.now().strftime('%Y-%m-%d-%H-%M-%S')
            
            # Create the processed filename with the required format
            if custom_name:
                # If the user provided a name, use it at the beginning
                processed_filename = f"{custom_name}_capture_{timestamp}_processed.txt"
            else:
                # If the user pressed "Cancel" or left the field empty, use the default format
                processed_filename = f"capture_{timestamp}_processed.txt"
                
            processed_filepath = os.path.join(self.capture_dir, processed_filename)
            
            # Write back the filtered content
            with open(processed_filepath, 'w', encoding='utf-8') as f:
                f.write(''.join([''.join(block) for block in unique_blocks]))
                
            print(f"Original blocks: {len(blocks)}, After processing: {len(unique_blocks)}")
            print(f"Processed file saved as: {processed_filepath}")
            
            # Log additional success information
            print(f"File successfully processed at {datetime.now()}")
            print(f"Original file: {filepath}")
            print(f"New processed file: {processed_filepath}")

            # Add debug logging if enabled
            if hasattr(self, 'debug_enabled') and self.debug_enabled.get():
                self.log_debug(f"Successfully processed file '{filepath}' to '{processed_filepath}'")
                
            return processed_filepath  # Return the path to the new file
            
        except Exception as e:
            print(f"Error in post-processing: {str(e)}")
            import traceback
            traceback.print_exc()
            return None
        
if __name__ == "__main__":
    try:
        # Set up early logging before any prints
        import sys
        import os
        from datetime import datetime
        
        # Determine script path
        if getattr(sys, 'frozen', False):
            script_path = os.path.dirname(sys.executable)
        else:
            script_path = os.path.dirname(os.path.abspath(__file__))
        
        # Create logs directory
        logs_dir = os.path.join(script_path, "logs")
        os.makedirs(logs_dir, exist_ok=True)
        
        # Create log file with timestamp
        timestamp = datetime.now().strftime('%Y-%m-%d %H-%M-%S')
        log_filename = f"log_{timestamp}.txt"
        log_file_path = os.path.join(logs_dir, log_filename)
        
        # Open log file and redirect stdout
        log_file = open(log_file_path, 'w', encoding='utf-8', buffering=1)
        sys.stdout = log_file
        print(f"Logs directory created at: {logs_dir}")
        
        print(f"Logging started at {datetime.now()}")
        
        print(f"CaptiOCR Version: {VERSION}")
        
        # Now create the application
        print("Creating application instance...")
        app = ScreenOCR()
        
        print("Running application...")
        app.run()
        
    except Exception as e:
        # Print the error to the log if possible
        print(f"Critical error: {str(e)}")
        
        # Make sure we restore stdout before displaying message to user
        if 'log_file' in locals() and log_file:
            sys.stdout = sys.__stdout__  # Restore to system default stdout
        
        # Show error in UI if possible
        input("Press Enter to exit...")
        
    finally:
        # Make sure log file is closed
        if 'log_file' in locals() and log_file:
            log_file.close()