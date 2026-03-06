#!/bin/bash

# TranscriptX Docker Data Setup Script
# Downloads all necessary data for the Docker environment

set -e

echo "📥 Setting up TranscriptX data in Docker..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Download all necessary data
download_data() {
    print_status "Downloading NLTK data..."
    docker run --rm transcriptx:prod python -c "
import nltk
nltk.download('punkt')
nltk.download('punkt_tab')
nltk.download('stopwords')
nltk.download('wordnet')
nltk.download('averaged_perceptron_tagger')
nltk.download('maxent_ne_chunker')
nltk.download('words')
nltk.download('vader_lexicon')
print('NLTK data downloaded successfully')
"

    print_status "Downloading TextBlob corpora..."
    docker run --rm transcriptx:prod python -c "
from textblob.download_corpora import download_all
download_all()
print('TextBlob corpora downloaded successfully')
"

    print_status "Downloading spaCy models..."
    docker run --rm transcriptx:prod python -c "
import spacy
spacy.cli.download('en_core_web_sm')
spacy.cli.download('en_core_web_md')
print('spaCy models downloaded successfully')
"

    print_status "Downloading NRC Lexicon..."
    docker run --rm transcriptx:prod python -c "
from nrclex import NRCLex
# Test NRCLex to ensure it's working
test_text = 'I am happy'
nrc = NRCLex(test_text)
print('NRC Lexicon working successfully')
"
}

# Create a data volume for persistent storage
create_data_volume() {
    print_status "Creating data volume for persistent storage..."
    docker volume create transcriptx-data
    print_success "Data volume created"
}

# Test the setup
test_setup() {
    print_status "Testing data setup..."
    
    # Test basic functionality
    docker run --rm -v transcriptx-data:/app/data transcriptx:prod python -c "
import transcriptx
import nltk
import spacy
from nrclex import NRCLex
from textblob import TextBlob

# Test NLTK
nltk.data.find('tokenizers/punkt')
nltk.data.find('corpora/stopwords')

# Test spaCy
nlp = spacy.load('en_core_web_sm')
doc = nlp('Hello world')
print('spaCy working:', len(doc))

# Test NRC Lexicon
nrc = NRCLex('I am happy')
print('NRC Lexicon working:', len(nrc.affect_frequencies))

# Test TextBlob
blob = TextBlob('I am happy')
print('TextBlob working:', blob.sentiment.polarity)

print('✅ All data components working correctly')
"
}

# Show usage instructions
show_instructions() {
    echo ""
    echo "🎉 Data setup complete!"
    echo ""
    echo "📋 Next steps:"
    echo "  1. Start development environment: ./scripts/docker-dev.sh"
    echo "  2. Start production environment: ./scripts/docker-prod.sh"
    echo "  3. Start web viewer: ./scripts/docker-web.sh"
    echo ""
    echo "🔧 Data is stored in Docker volume: transcriptx-data"
    echo "📁 You can access it by mounting the volume in your containers"
    echo ""
}

# Main execution
main() {
    echo "🚀 TranscriptX Data Setup"
    echo "========================"
    echo ""
    
    download_data
    create_data_volume
    test_setup
    show_instructions
}

# Run main function
main "$@" 