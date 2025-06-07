import os
import re
import shutil
import hashlib
import warnings
import logging
import contextlib
from datetime import datetime
from pathlib import Path
from typing import List, Set, Dict, Tuple
from tqdm import tqdm
import chardet
from PyPDF2 import PdfReader
from bs4 import BeautifulSoup

# Suppress PyPDF2 logging
logging.getLogger('PyPDF2').setLevel(logging.ERROR)

@contextlib.contextmanager
def suppress_warnings():
    """Context manager to suppress various warnings."""
    with warnings.catch_warnings():
        # Suppress all warnings from PyPDF2 and its submodules
        warnings.filterwarnings("ignore", category=UserWarning)
        warnings.filterwarnings("ignore", category=DeprecationWarning)
        warnings.filterwarnings("ignore", module="PyPDF2.*")
        # Suppress BeautifulSoup warnings
        warnings.filterwarnings("ignore", module="bs4")
        yield

def init_logging():
    """Initialize logging configuration."""
    # Suppress all logging below ERROR level for PyPDF2
    for logger_name in ['PyPDF2', 'pdfminer', 'pdfminer.pdfdocument']:
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.ERROR)

# Initialize logging
init_logging()

# Configuration
SOURCE_DIR = "./source_documents"  # Replace with your source directory
DEST_DIR = "./sorted_documents"      # Replace with your destination directory

class DocumentSorter:
    def __init__(self, source_dir: str, dest_base_dir: str, max_files_per_folder: int = 500):
        self.source_dir = Path(source_dir)
        self.dest_base_dir = Path(dest_base_dir)
        self.max_files_per_folder = max_files_per_folder
        self.category_mapping = {
            # Documents
            '.doc': 'documents',
            '.docx': 'documents',
            '.pages': 'documents',
            '.odt': 'documents',
            '.rtf': 'documents',
            
            # Spreadsheets
            '.xls': 'spreadsheets',
            '.xlsx': 'spreadsheets',
            '.numbers': 'spreadsheets',
            '.ods': 'spreadsheets',
            '.csv': 'spreadsheets',
            
            # Presentations
            '.ppt': 'presentations',
            '.pptx': 'presentations',
            '.key': 'presentations',
            '.odp': 'presentations',
            
            # Notes and text files
            '.txt': 'notes',
            '.md': 'notes',
            '.rtf': 'notes',
            
            # Web files (non-bookmarks)
            '.html': 'web',
            '.htm': 'web',
            '.mht': 'web',
            '.url': 'web',
            '.webloc': 'web',
            
            # Archives
            '.zip': 'archives',
            '.rar': 'archives',
            '.7z': 'archives',
            '.tar': 'archives',
            '.gz': 'archives',
            '.bz2': 'archives',
            
            # Images
            '.jpg': 'images',
            '.jpeg': 'images',
            '.png': 'images',
            '.gif': 'images',
            '.bmp': 'images',
            '.tiff': 'images',
            '.webp': 'images',
            
            # Audio
            '.mp3': 'audio',
            '.wav': 'audio',
            '.aac': 'audio',
            '.m4a': 'audio',
            '.ogg': 'audio',
            '.flac': 'audio',
            
            # Video
            '.mp4': 'video',
            '.mov': 'video',
            '.avi': 'video',
            '.mkv': 'video',
            '.wmv': 'video',
            '.flv': 'video',
            
            # Code
            '.py': 'code',
            '.js': 'code',
            '.java': 'code',
            '.cpp': 'code',
            '.c': 'code',
            '.h': 'code',
            '.css': 'code',
            '.php': 'code',
            '.rb': 'code',
            '.swift': 'code',
            '.go': 'code',
            '.rs': 'code',
            
            # Configuration
            '.json': 'config',
            '.xml': 'config',
            '.yaml': 'config',
            '.yml': 'config',
            '.ini': 'config',
            '.conf': 'config',
            '.env': 'config',
            
            # Database
            '.sql': 'database',
            '.db': 'database',
            '.sqlite': 'database',
            '.sqlite3': 'database'
        }
        # Define binary document formats
        self.binary_formats = {
            '.doc', '.rtf', '.docx', '.odt', '.pdf', '.pages',  # Documents
            '.xls', '.xlsx', '.xlsm', '.ods', '.numbers',  # Spreadsheets
            '.key', '.ppt', '.pptx', '.odp', '.keynote'  # Presentations
        }
        # Get all supported extensions from the category mapping
        self.document_extensions = set(self.category_mapping.keys())
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
        # If no timestamp found or parsing failed, use file modification time
        return datetime(1970, 1, 1)

    def get_all_files(self) -> List[Path]:
        """Get all supported document files recursively from the source directory."""
        all_files = []
        for ext in self.document_extensions:
            files = list(self.source_dir.rglob(f'*{ext}'))
            files.extend(list(self.source_dir.rglob(f'*{ext.upper()}')))
            all_files.extend(files)
        return all_files

    def detect_encoding(self, file_path: Path) -> str:
        """Detect the encoding of a text file."""
        try:
            with open(file_path, 'rb') as f:
                raw_data = f.read(4096)  # Read first 4KB
                if not raw_data:  # Empty file
                    return 'utf-8'
                result = chardet.detect(raw_data)
                return result['encoding'] if result['encoding'] else 'utf-8'
        except Exception:
            return 'utf-8'

    def read_file_content(self, file_path: Path) -> str:
        """Read file content with proper encoding handling."""
        # Handle binary document formats
        if file_path.suffix.lower() in self.binary_formats:
            try:
                with open(file_path, 'rb') as f:
                    content = f.read()
                    # For binary files, we'll use the raw bytes for hashing
                    return content.hex()
            except Exception:
                return ""

        # Regular file handling for text files (including bookmarks)
        encodings = ['utf-8', 'latin1', 'cp1252', 'iso-8859-1']
        
        # First try detected encoding
        detected = self.detect_encoding(file_path)
        if detected and detected not in encodings:
            encodings.insert(0, detected)

        # Try each encoding
        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    return f.read()
            except UnicodeDecodeError:
                continue
            except Exception:
                return ""
        
        # If all encodings fail, try one last time with utf-8 and ignore errors
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
        except Exception:
            return ""

    def normalize_content(self, content: str) -> str:
        """Normalize text content by removing whitespace and converting to lowercase."""
        # Remove all whitespace and convert to lowercase
        return ''.join(content.split()).lower()

    def compute_file_hash(self, file_path: Path) -> Tuple[str, str]:
        """Compute normalized content hash for a text file."""
        try:
            content = self.read_file_content(file_path)
            if not content:  # Empty or unreadable file
                return str(file_path), None
            
            # For binary formats, use the content directly (it's already in hex format)
            if file_path.suffix.lower() in self.binary_formats:
                file_hash = content  # content is already in hex format for binary files
            else:
                # Normalize content before hashing for text files (including bookmarks)
                normalized_content = self.normalize_content(content)
                file_hash = hashlib.sha256(normalized_content.encode('utf-8')).hexdigest()
            
            return str(file_path), file_hash
        except Exception:
            return str(file_path), None

    def find_duplicates(self, files: List[Path]) -> Dict[str, List[str]]:
        """Find duplicate files based on content hashing."""
        hash_dict = {}  # hash -> first file path
        duplicates = {}  # hash -> list of duplicate file paths

        for file_path in files:
            path_str, file_hash = self.compute_file_hash(file_path)
            if file_hash is None:
                continue
        
            if file_hash in hash_dict:
                duplicates.setdefault(file_hash, []).append(path_str)
            else:
                hash_dict[file_hash] = path_str

        return duplicates

    def is_bookmark_file(self, file_path: Path) -> bool:
        """Check if an HTML file is a bookmark file by looking at its content."""
        try:
            with suppress_warnings():
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                    # Try parsing as XML first
                    try:
                        soup = BeautifulSoup(content, 'xml')
                    except:
                        # Fall back to HTML parser if XML fails
                        soup = BeautifulSoup(content, 'lxml')
                    
                    # First check the title
                    title = soup.find('title')
                    if title and re.search(r'bookmarks?', title.text, re.I):
                        return True
                    
                    # If no title match, check for common bookmark attributes
                    bookmark_links = soup.find_all('a', {'add_date': True}) or soup.find_all('a', {'last_modified': True})
                    if bookmark_links:
                        return True
                    
                    return False
        except Exception:
            # Fall back to filename-based detection
            return 'bookmark' in file_path.name.lower()

    def get_pdf_page_count(self, file_path: Path) -> int:
        """Get the number of pages in a PDF file."""
        try:
            with suppress_warnings():
                with open(file_path, 'rb') as f:
                    pdf = PdfReader(f)
                    return len(pdf.pages)
        except Exception:
            return 0

    def get_file_category(self, file_path: Path) -> str:
        """Determine the category for a file based on extension, content, and metadata."""
        ext = file_path.suffix.lower()
        
        # Special handling for PDF files based on page count
        if ext == '.pdf':
            page_count = self.get_pdf_page_count(file_path)
            return 'ebooks' if page_count > 5 else 'pdfs'
        
        # Special handling for HTML files to detect bookmarks
        if ext in ['.html', '.htm', '.url', '.webloc']:
            if self.is_bookmark_file(file_path):
                return 'bookmarks'
            return 'web'
        
        # Use the regular category mapping for other files
        return self.category_mapping.get(ext, 'other')

    def get_next_batch_folder(self, category: str) -> Path:
        """Create and return the next available batch folder for the given category."""
        category_dir = self.dest_base_dir / category
        category_dir.mkdir(parents=True, exist_ok=True)
        
        while True:
            folder = category_dir / f"batch_{self.current_folder_num:03d}"
            folder.mkdir(parents=True, exist_ok=True)
            
            # Count files in this folder
            file_count = sum(1 for _ in folder.glob('*'))
            
            if file_count < self.max_files_per_folder:
                return folder
            
            self.current_folder_num += 1

    def organize_files(self, files: Set[Path]):
        """Move files to destination folders with max files per folder limit."""
        self.dest_base_dir.mkdir(parents=True, exist_ok=True)
        
        # Group files by category
        files_by_category = {}
        for file_path in files:
            category = self.get_file_category(file_path)
            if category not in files_by_category:
                files_by_category[category] = []
            files_by_category[category].append(file_path)
        
        # Process each category
        for category, sorted_files in files_by_category.items():
            # Reset folder numbering for each category
            self.current_folder_num = 1
            
            for file_path in tqdm(sorted_files, desc=f"Processing {category} files"):
                dest_folder = self.get_next_batch_folder(category)
                try:
                    shutil.move(str(file_path), str(dest_folder / file_path.name))
                    self.processed_files.add(file_path)
                except Exception:
                    continue

    def clean_source_directory(self, duplicates: Dict[str, List[str]]):
        """Clean up the source directory by removing processed files, duplicates, and empty directories."""
        # Remove processed files and duplicates
        files_removed = 0
        for file_path in tqdm(self.processed_files, desc="Removing processed files"):
            try:
                if file_path.exists():
                    os.remove(file_path)
                    files_removed += 1
            except Exception:
                continue

        # Remove duplicate files
        duplicates_removed = 0
        duplicate_files = [path for paths in duplicates.values() for path in paths]
        for path_str in tqdm(duplicate_files, desc="Removing duplicate files"):
            try:
                path = Path(path_str)
                if path.exists():
                    os.remove(path)
                    duplicates_removed += 1
            except Exception:
                continue

        # Remove .DS_Store files and empty directories
        for dirpath, dirnames, filenames in os.walk(str(self.source_dir), topdown=False):
            ds_store = Path(dirpath) / '.DS_Store'
            if ds_store.exists():
                try:
                    os.remove(ds_store)
                except Exception:
                    continue

        # Remove empty directories
        empty_dirs_removed = 0
        for dirpath, dirnames, filenames in os.walk(str(self.source_dir), topdown=False):
            if dirpath == str(self.source_dir):
                continue
            try:
                if not os.listdir(dirpath):
                    os.rmdir(dirpath)
                    empty_dirs_removed += 1
            except Exception:
                continue

        print(f"\nCleanup complete:")
        print(f"- Removed {files_removed} processed files")
        print(f"- Removed {duplicates_removed} duplicate files")
        print(f"- Removed {empty_dirs_removed} empty directories")

def main():
    """Main function to run the document file sorter."""
    # Get source and destination directories from environment or use defaults
    source_dir = os.environ.get('DOCUMENT_SORT_SOURCE', SOURCE_DIR)
    dest_dir = os.environ.get('DOCUMENT_SORT_DEST', DEST_DIR)

    # Create DocumentSorter instance
    sorter = DocumentSorter(source_dir, dest_dir)

    # Get all document files
    print("\nFinding files...")
    all_files = sorter.get_all_files()
    total_files = len(all_files)
    print(f"Found {total_files} files")

    if total_files == 0:
        print("No files to process. Exiting.")
        return

    # Process files and compute hashes
    print("\nProcessing files...")
    unique_files = set()
    processed_hashes = set()
    
    for file_path in tqdm(all_files, desc="Computing file hashes"):
        path_str, file_hash = sorter.compute_file_hash(file_path)
        if file_hash is None:
            continue
        
        if file_hash not in processed_hashes:
            unique_files.add(file_path)
            processed_hashes.add(file_hash)

    # Find duplicates
    duplicates = sorter.find_duplicates(list(all_files))
    print(f"\nFound {len(unique_files)} unique files")
    print(f"Found {len(duplicates)} duplicate sets")

    # Organize unique files
    print("\nOrganizing files...")
    sorter.organize_files(unique_files)

    # Clean up source directory
    sorter.clean_source_directory(duplicates)
    print("\nProcessing complete!")
    print(f"Processed {total_files} files")
    print(f"Found {len(duplicates)} duplicate sets")
    print(f"Organized {len(unique_files)} unique files")

if __name__ == "__main__":
    main()
