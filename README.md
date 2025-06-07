# Media Batch Manager

A toolkit for organizing and deduplicating media files and documents.

## Overview

media-batch-manager is a collection of Python utilities designed to help you organize large collections of files. It includes two main tools:

- **ImageSort**: Organizes and deduplicates images and videos using perceptual hashing
- **DocumentSort**: Organizes and deduplicates documents using content-based hashing

Both tools can process large collections of files, identify and remove duplicates, and organize the remaining files into manageable batches.

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/media-batch-manager.git
cd media-batch-manager

# Install dependencies
pip install -r requirements.txt
```

### Running the Tools

#### Image Sorter

```bash
python sort_image.py
```

#### Document Sorter

```bash
python sort_document.py
```

## Features

### Common Features

- **Intelligent deduplication**: Identifies and removes duplicate files
- **Batch organization**: Groups files into folders with a configurable maximum number of files per folder (default limit: 500 files per folder)
- **Progress tracking**: Shows detailed progress bars for long-running operations
- **Source cleanup**: Removes processed files and empty directories after successful processing
- **Detailed statistics**: Provides summary statistics after processing

### ImageSort Specific Features

- **Perceptual hashing**: Uses image hashing algorithms to identify visually similar images
- **Support for HEIC format**: Handles Apple's HEIC image format
- **Video file support**: Processes common video formats

### DocumentSort Specific Features

- **Content-based deduplication**: Compares normalized document content to find duplicates
- **Automatic encoding detection**: Handles various text encodings correctly
- **Smart categorization**: Organizes files into categories based on file type
- **PDF processing**: Extracts and analyzes text content from PDF files

## How It Works

### ImageSort Process

1. Scans the source directory for supported image and video files
2. Computes perceptual hashes for images and content hashes for other files
3. Identifies and removes duplicate files
4. Organizes unique files into batch folders
5. Cleans up the source directory

### DocumentSort Process

1. Scans the source directory for document files
2. Analyzes document content with appropriate encoding detection
3. Computes normalized content hashes to identify duplicates
4. Categorizes files by type (documents, spreadsheets, presentations, etc.)
5. Organizes files into category-specific batch folders
6. Cleans up the source directory

## Configuration

Both tools use default source and destination directories that can be customized:

```python
# In sort_image.py
SOURCE_DIR = "./source_images"  # Change this to your source directory
DEST_DIR = "./sorted_images"    # Change this to your destination directory

# In sort_document.py
SOURCE_DIR = "./source_documents"  # Change this to your source directory
DEST_DIR = "./sorted_documents"    # Change this to your destination directory
```

You can also set these directories using environment variables for the document sorter:

```bash
export DOCUMENT_SORT_SOURCE="./source_documents"
export DOCUMENT_SORT_DEST="./sorted_documents"
```

## Supported File Formats

### Images

- JPEG/JPG, PNG, GIF, BMP, WebP, SVG, TIFF/TIF, HEIC

### Videos

- MP4, MOV, AVI, MKV, WMV, FLV, WebM, MPG/MPEG, M4V

### Documents

- Office: DOC, DOCX, XLS, XLSX, PPT, PPTX, ODT, ODS, ODP
- Text: TXT, MD, RTF, CSV, JSON, XML, YAML, LOG
- Web: HTML, HTM, CSS, JS
- Code: Various programming language files
- Other: PDF, Archives (ZIP, RAR, etc.)
