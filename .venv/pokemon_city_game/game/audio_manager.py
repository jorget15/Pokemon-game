import pygame
import random
import json, pygame, os, logging
from os import path


class MusicManager:
    def __init__(self, starting_track: str, music_dir: str, maps_json_path: str | None = None):
        # Debug: Print initial paths
        print(f"[MusicManager] Initializing with music_dir: {music_dir}")
        print(f"[MusicManager] maps_json_path: {maps_json_path}")
        
        self.maps_json_path = (
            maps_json_path or os.path.join(os.path.dirname(__file__), "maps.json")
        )

        self.zone_music_map = self.create_zone_music_map()

        self.folder = music_dir
        self.base = starting_track  # Use the starting track name directly

        # Debug: Print available music files
        if os.path.exists(music_dir):
            files = os.listdir(music_dir)
            print(f"[MusicManager] Available music files: {files}")
        else:
            print(f"[MusicManager] WARNING: Music directory does not exist: {music_dir}")

        # Channels: channel(0) for main music, channel(1) for idle track.
        self.music_channel = None
        self.idle_channel = None

        # Loaded sounds
        self.main_sound = None  # The main track's Sound object
        self.idle_sound = None  # The currently playing idle track Sound object

        # Volume management
        self.normal_volume = 0.6
        self.muffled_volume = 0.2
        self.current_volume = self.normal_volume

        # For the blocking fade method
        self.fade_speed = 0.01

        # Tracks whether we've switched to an idle version
        self.is_idle_version = False

        # Load maps data (if provided) and build zone->music map
        self.maps_data = self.load_maps_data(maps_json_path)
        self.zone_music_map = self.create_zone_music_map()

        # Initialize mixer, channels, and load/play the base track
        pygame.mixer.init()
        self.init_channels()
        self.load_base_track()
        if self.main_sound:
            self.play_base_track()

    def load_maps_data(self, maps_json_path):
        """
        Loads the JSON for your maps (if provided).
        Each map entry can optionally have a "music" key for its track.
        """
        if not maps_json_path or not os.path.exists(maps_json_path):
            print(f"[MusicManager] Warning: maps.json not found at '{maps_json_path}'")
            return {}

        try:
            with open(maps_json_path, 'r') as f:
                maps_data = json.load(f)
                print(f"[MusicManager] Loaded maps data with {len(maps_data)} zones")
                return maps_data
        except Exception as e:
            print(f"[MusicManager] Error loading maps data: {e}")
            return {}

    def create_zone_music_map(self) -> dict[str, str]:
        """Return {'ZoneName': 'music_file', ...}.
           If maps.json is missing or bad, fall back to a single default entry.
           Track names are stored without .mp3 extension to avoid double extension.
        """
        zone_music = {}

        # 1️⃣  Try to load maps.json
        if self.maps_json_path and os.path.isfile(self.maps_json_path):
            try:
                with open(self.maps_json_path, "r", encoding="utf-8") as f:
                    maps_data = json.load(f)

                for zone, data in maps_data.items():
                    # field is "music": "coroTown" (your JSON) ➜ build a filename
                    track_name = data.get("music", "").strip()
                    if track_name:
                        # Remove .mp3 extension if it exists and store clean name
                        if track_name.endswith('.mp3'):
                            track_name = track_name[:-4]
                        zone_music[zone] = track_name
            except Exception as exc:
                logging.warning("[MusicManager] Could not parse %s: %s",
                                self.maps_json_path, exc)

        # 2️⃣  Fallback if nothing loaded
        if not zone_music:
            logging.warning("[MusicManager] maps.json not found or empty – "
                            "falling back to default 'CoroTown'")
            zone_music = {"coroTown": "CoroTown"}  # <- your default zone/music

        return zone_music

    def get_zone_info(self, zone_name):
        """
        If you want to get additional data from maps.json for a zone,
        you can call this. For example, obstacles, events, etc.
        """
        return self.maps_data.get(zone_name, {})

    def init_channels(self):
        """
        Creates two dedicated mixer Channels:
          - channel(0) for main (base) track
          - channel(1) for idle track
        """
        self.music_channel = pygame.mixer.Channel(0)
        self.idle_channel = pygame.mixer.Channel(1)

    def get_full_path(self, name):
        """Return the path to an .mp3 file inside self.folder.
        First tries exact match, then tries case-insensitive and underscore/space variations."""
        exact_path = path.join(self.folder, f"{name}.mp3")
        if path.exists(exact_path):
            return exact_path
        
        # Try alternative matching
        alt_path = self.find_music_file_case_insensitive(name)
        if alt_path:
            return alt_path
            
        # Return original path if no alternatives found (will fail gracefully elsewhere)
        return exact_path

    def load_base_track(self):
        """
        Loads self.base track into main_sound if it exists on disk.
        """
        track_path = self.get_full_path(self.base)
        try:
            if path.exists(track_path):
                self.main_sound = pygame.mixer.Sound(track_path)
                print(f"[MusicManager] Loaded main track: {self.base} from {track_path}")
            else:
                print(f"[MusicManager] Warning: {track_path} not found.")
                # Try to find alternative case variations
                alt_path = self.find_music_file_case_insensitive(self.base)
                if alt_path:
                    self.main_sound = pygame.mixer.Sound(alt_path)
                    print(f"[MusicManager] Found alternative: {alt_path}")
                else:
                    print(f"[MusicManager] No alternatives found for {self.base}")
        except Exception as e:
            print(f"[MusicManager] Error loading base track: {e}")

    def find_music_file_case_insensitive(self, track_name):
        """
        Try to find a music file with case-insensitive matching and underscore/space conversion.
        Returns the full path if found, None otherwise.
        """
        if not os.path.exists(self.folder):
            return None
            
        try:
            files = os.listdir(self.folder)
            
            # Try exact match first (case-insensitive)
            target_filename = f"{track_name}.mp3".lower()
            for file in files:
                if file.lower() == target_filename:
                    return os.path.join(self.folder, file)
            
            # Try with underscore to space conversion
            track_with_spaces = track_name.replace('_', ' ')
            target_filename_spaces = f"{track_with_spaces}.mp3".lower()
            for file in files:
                if file.lower() == target_filename_spaces:
                    return os.path.join(self.folder, file)
            
            # Try with space to underscore conversion
            track_with_underscores = track_name.replace(' ', '_')
            target_filename_underscores = f"{track_with_underscores}.mp3".lower()
            for file in files:
                if file.lower() == target_filename_underscores:
                    return os.path.join(self.folder, file)
                    
        except Exception as e:
            print(f"[MusicManager] Error searching for alternative files: {e}")
        
        return None

    def play_base_track(self):
        """
        Play the main track on channel 0, looping forever, at current_volume.
        """
        if self.main_sound and self.music_channel:
            self.music_channel.play(self.main_sound, loops=-1)
            self.music_channel.set_volume(self.current_volume)
            print(f"[MusicManager] Playing base track: {self.base} on channel 0")

    def stop_base_track(self):
        """Stop whatever is playing on channel 0."""
        if self.music_channel:
            self.music_channel.stop()
            print("[MusicManager] Stopped base track on channel 0")

    def set_zone_music(self, zone_name):
        """
        Switch music based on zone_name, referencing self.zone_music_map for the track name.
        If track_name differs from self.base, stop old and load/play new.
        """
        track_name = self.zone_music_map.get(zone_name, zone_name.lower())
        
        # Remove .mp3 extension if it exists to avoid double extension
        if track_name.endswith('.mp3'):
            track_name = track_name[:-4]

        if track_name != self.base:
            print(f"[MusicManager] Switching to zone: {zone_name}, track: {track_name}")
            self.base = track_name
            self.stop_base_track()
            self.load_base_track()
            if self.main_sound:
                self.play_base_track()
                # Reset idle flags
                self.is_idle_version = False
                self.current_volume = self.normal_volume

    def trigger_idle_audio(self, idle_option):
        """
        Called when the player is idle.
          1 -> Muffle the base track on channel 0
          2 -> Play idle track "idleDaniel" on channel 1
          3 -> Play idle track "idle_track_2" on channel 1
        """
        if not self.music_channel:
            return

        print(f"[MusicManager] trigger_idle_audio called with option {idle_option}")

        # Option 1: keep main track playing, just fade to muffled
        if idle_option == 1:
            print("[MusicManager] Idle option 1: muffling base (channel 0 stays on)")
            self.fade_to(self.muffled_volume)

        # Option 2 or 3: load a separate track on channel 1
        elif idle_option == 2:
            print("[MusicManager] Idle option 2: play idleDaniel on channel 1")
            self.play_idle_track("idleDaniel")
        elif idle_option == 3:
            print("[MusicManager] Idle option 3: play idle_track_2 on channel 1")
            self.play_idle_track("idle_track_2")

        self.is_idle_version = True

    def play_idle_track(self, track_name):
        """
        Load track_name.mp3 and play it on channel 1 at muffled volume.
        Also sets channel 0 volume to 0 if you want no overlap,
        or you could just fade it out fully if you prefer.
        """
        if self.idle_channel:
            self.idle_channel.stop()

        full_path = self.get_full_path(track_name)
        if path.exists(full_path):
            try:
                self.idle_sound = pygame.mixer.Sound(full_path)
                self.idle_channel.play(self.idle_sound, loops=-1)
                self.idle_channel.set_volume(self.muffled_volume)
                # Lower or stop channel 0 if you don't want overlap
                # E.g.: self.music_channel.set_volume(0.0)
                print(f"[MusicManager] Idle track playing: {track_name} on channel 1")
            except Exception as e:
                print(f"[MusicManager] Error loading idle track: {e}")
        else:
            print(f"[MusicManager] Idle track not found: {track_name}")
            # Try case-insensitive search
            alt_path = self.find_music_file_case_insensitive(track_name)
            if alt_path:
                try:
                    self.idle_sound = pygame.mixer.Sound(alt_path)
                    self.idle_channel.play(self.idle_sound, loops=-1)
                    self.idle_channel.set_volume(self.muffled_volume)
                    print(f"[MusicManager] Found alternative idle track: {alt_path}")
                except Exception as e:
                    print(f"[MusicManager] Error loading alternative idle track: {e}")

    def reset_to_base_audio(self):
        """
        Called when the player stops being idle or moves again.
        If we used idle track on channel 1, stop it and fade main track up.
        If we used idle option 1, just fade the main track from muffled to normal.
        """
        if self.is_idle_version:
            print("[MusicManager] Returning to base audio")

            # Stop idle track if it's playing
            if self.idle_channel and self.idle_channel.get_busy():
                self.idle_channel.stop()
                print("[MusicManager] Stopped idle track on channel 1")

            # Ensure main track is playing
            if (not self.music_channel.get_busy()) and self.main_sound:
                self.play_base_track()

            # Fade main track back to normal volume
            self.fade_to(self.normal_volume)
            self.current_volume = self.normal_volume
            self.is_idle_version = False

    def fade_to(self, target_volume):
        """
        Blockingly fade from current_volume to target_volume in small steps.
        Using time.delay(30) will freeze the game for ~300ms total.
        """
        if not self.music_channel:
            return

        steps = 10
        volume_step = (target_volume - self.current_volume) / steps
        print(f"[MusicManager] Fading from {self.current_volume} to {target_volume}")

        for _ in range(steps):
            self.current_volume += volume_step
            self.current_volume = max(0.0, min(1.0, self.current_volume))
            self.music_channel.set_volume(self.current_volume)
            pygame.time.delay(30)

    @staticmethod
    def choose_idle_option():
        """
        Weighted random pick for idle option:
          1 -> 50% chance
          2 -> 25% chance
          3 -> 25% chance
        Adjust as you like.
        """
        return random.choices([1, 2, 3], weights=[5, 2, 2])[0]
