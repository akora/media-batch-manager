import os
import shutil
from pathlib import Path
from typing import Dict, List, Set, Tuple
import imagehash
from PIL import Image
from tqdm import tqdm
import re
from datetime import datetime
import hashlib
import pillow_heif  # For HEIC support

# Register HEIF opener with PIL
pillow_heif.register_heif_opener()

# Configuration
SOURCE_DIR = "./source_images"  # Replace with your source directory
DEST_DIR = "./sorted_images"      # Replace with your destination directory

class FileSorter:
    def __init__(self, source_dir: str, dest_base_dir: str, max_files_per_folder: int = 500):
        self.source_dir = Path(source_dir)
        self.dest_base_dir = Path(dest_base_dir)
        self.max_files_per_folder = max_files_per_folder
        self.image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg', '.tiff', '.tif', '.heic'}
        self.video_extensions = {'.mp4', '.mov', '.avi', '.mkv', '.wmv', '.flv', '.webm', '.mpg', '.mpeg', '.m4v'}
        self.text_extensions = {'.txt', '.md', '.csv', '.json', '.xml', '.log', '.py', '.js', '.html', '.css', '.mm'}
        self.processed_files = set()  # Keep track of processed files
        self.current_folder_num = 1
        self.timestamp_pattern = re.compile(r'^(\d{8}-\d{6})')

    def extract_timestamp(self, filename: str) -> datetime:
        """Extract timestamp from filename and convert to datetime object."""
        try:
            match = self.timestamp_pattern.match(filename)
            if match:
                timestamp_str = match.group(1)  # YYYYMMDD-HHMMSS
                return datetime.strptime(timestamp_str, '%Y%m%d-%H%M%S')
        except Exception:
            pass
        # If no timestamp found or parsing failed, use a default old date
        return datetime(1970, 1, 1)

    def get_all_files(self) -> List[Path]:
        """Get all supported files recursively from the source directory and its subdirectories."""
        all_files = []
        all_extensions = self.image_extensions | self.video_extensions | self.text_extensions
        
        for ext in all_extensions:
            all_files.extend(self.source_dir.rglob(f'*{ext}'))
            all_files.extend(self.source_dir.rglob(f'*{ext.upper()}'))
        
        # Sort files by timestamp
        return sorted(all_files, key=lambda x: self.extract_timestamp(x.name))

    def compute_file_hash(self, file_path: Path) -> Tuple[str, str]:
        """Compute hash for a file based on its type."""
        try:
            if file_path.suffix.lower() in self.image_extensions:
                # Use perceptual hash for images
                with Image.open(file_path) as img:
                    if img.mode != 'RGB':
                        img = img.convert('RGB')
                    hash_value = str(imagehash.average_hash(img))
            else:
                # For non-image files (videos and text), use a more robust content hash
                file_stats = os.stat(file_path)
                file_size = file_stats.st_size
                
                # For larger files (like videos), read in chunks
                chunk_size = 1024 * 1024  # 1MB chunks
                md5_hash = hashlib.md5()
                
                # Always include file size in hash to distinguish different sized files
                md5_hash.update(str(file_size).encode())
                
                with open(file_path, 'rb') as f:
                    # For very large files (like videos), read from start and end
                    if file_size > chunk_size * 2:
                        # Read first chunk
                        md5_hash.update(f.read(chunk_size))
                        # Read last chunk
                        f.seek(-chunk_size, 2)
                        md5_hash.update(f.read(chunk_size))
                    else:
                        # For smaller files, read entire content
                        md5_hash.update(f.read())
                
                hash_value = md5_hash.hexdigest()
            
            return str(file_path), hash_value
        except Exception as e:
            print(f"Error processing {file_path}: {str(e)}")
            return str(file_path), None

    def find_duplicates(self, files: List[Path], hash_threshold: int = 0) -> Dict[str, List[str]]:
        """Find duplicate files based on hashing."""
        hash_dict = {}
        duplicates = {}

        print("Computing file hashes...")
        for file_path in tqdm(files):
            path_str, file_hash = self.compute_file_hash(file_path)
            if file_hash is None:
                continue

            if file_path.suffix.lower() in self.image_extensions:
                # For images, check similarity with threshold
                found_similar = False
                for existing_hash in hash_dict:
                    # Only compare image hashes
                    if len(existing_hash) == len(file_hash):  # Simple check if it's an image hash
                        if sum(c1 != c2 for c1, c2 in zip(file_hash, existing_hash)) <= hash_threshold:
                            duplicates.setdefault(existing_hash, []).append(path_str)
                            found_similar = True
                            break
                
                if not found_similar:
                    hash_dict[file_hash] = path_str
            else:
                # For non-image files, use exact hash matching
                if file_hash in hash_dict:
                    duplicates.setdefault(file_hash, []).append(path_str)
                else:
                    hash_dict[file_hash] = path_str

        return duplicates

    def get_next_batch_folder(self) -> Path:
        """Create and return the next available batch folder."""
        while True:
            folder = self.dest_base_dir / f"batch_{self.current_folder_num:03d}"
            folder.mkdir(parents=True, exist_ok=True)
            
            # Count files in this folder
            file_count = sum(1 for _ in folder.glob('*'))
            
            if file_count < self.max_files_per_folder:
                return folder
            
            self.current_folder_num += 1

    def organize_files(self, unique_files: Set[Path]):
        """Move files to destination folders with max files per folder limit."""
        self.dest_base_dir.mkdir(parents=True, exist_ok=True)
        
        # Sort files by timestamp
        sorted_files = sorted(unique_files, key=lambda x: self.extract_timestamp(x.name))
        
        # Find the first available folder number
        existing_folders = list(self.dest_base_dir.glob('batch_*'))
        if existing_folders:
            last_folder = max(existing_folders)
            try:
                self.current_folder_num = int(last_folder.name.split('_')[1]) + 1
            except (ValueError, IndexError):
                self.current_folder_num = 1
        else:
            self.current_folder_num = 1
        
        print("Moving files to destination folders...")
        for file_path in tqdm(sorted_files):
            dest_folder = self.get_next_batch_folder()
            
            try:
                shutil.copy2(file_path, dest_folder / file_path.name)
                self.processed_files.add(file_path)
            except Exception as e:
                print(f"Error moving {file_path}: {str(e)}")

    def clean_source_directory(self):
        """Clean up the source directory by removing processed files and empty directories."""
        print("\nCleaning up source directory...")
        
        # Remove processed files
        for file_path in tqdm(self.processed_files, desc="Removing processed files"):
            try:
                if file_path.exists():  # Check if file still exists
                    os.remove(file_path)
            except Exception as e:
                print(f"Error removing {file_path}: {str(e)}")

        print("Removing .DS_Store files...")
        # Remove .DS_Store files before checking for empty directories
        for dirpath, dirnames, filenames in os.walk(str(self.source_dir), topdown=False):
            ds_store = Path(dirpath) / '.DS_Store'
            if ds_store.exists():
                try:
                    os.remove(ds_store)
                except Exception as e:
                    print(f"Error removing .DS_Store in {dirpath}: {str(e)}")

        print("Removing empty directories...")
        # Walk bottom-up through the directory tree to remove empty folders
        empty_dirs_removed = 0
        for dirpath, dirnames, filenames in os.walk(str(self.source_dir), topdown=False):
            if dirpath == str(self.source_dir):
                continue  # Skip the root source directory
            
            try:
                # Check if directory is empty (no files and no subdirectories)
                dir_contents = os.listdir(dirpath)
                if not dir_contents:  # Directory is empty
                    os.rmdir(dirpath)
                    empty_dirs_removed += 1
            except Exception as e:
                print(f"Error removing directory {dirpath}: {str(e)}")
        
        if empty_dirs_removed > 0:
            print(f"Removed {empty_dirs_removed} empty directories")

def main():
    source_dir = SOURCE_DIR
    dest_dir = DEST_DIR

    # Create sorter instance
    sorter = FileSorter(source_dir, dest_dir)
    
    # Get all files
    print("Finding files...")
    files = sorter.get_all_files()
    print(f"Found {len(files)} files")

    # Find duplicates
    duplicates = sorter.find_duplicates(files)
    
    # Print duplicate groups and remove duplicates
    duplicate_paths = set()
    if duplicates:
        print("\nFound duplicate files:")
        for hash_value, file_list in duplicates.items():
            if len(file_list) > 1:
                print(f"\nDuplicate group:")
                # Keep the first file, mark others as duplicates
                kept_file = file_list[0]
                print(f"  Keeping: {kept_file}")
                for file_path in file_list[1:]:
                    print(f"  Removing duplicate: {file_path}")
                    duplicate_paths.add(Path(file_path))
    else:
        print("\nNo duplicates found.")

    # Remove duplicate files
    print("\nRemoving duplicate files...")
    for dup_path in duplicate_paths:
        try:
            if dup_path.exists():
                dup_path.unlink()
                print(f"Removed: {dup_path}")
        except Exception as e:
            print(f"Error removing {dup_path}: {str(e)}")

    # Get unique files (excluding duplicates)
    unique_files = {Path(f) for f in files if Path(f) not in duplicate_paths}
    print(f"\nProcessing {len(unique_files)} unique files...")

    # Organize files
    print("\nOrganizing files...")
    sorter.organize_files(unique_files)
    print("Done organizing!")

    # Clean up source directory
    print("\nCleaning up source directory...")
    sorter.clean_source_directory()
    print("Cleanup complete!")

    # Print summary
    print("\nSummary:")
    print(f"Total files found: {len(files)}")
    print(f"Duplicates removed: {len(duplicate_paths)}")
    print(f"Unique files processed: {len(unique_files)}")

if __name__ == "__main__":
    main()
