# Enhanced AWS HealthOmics MCP Server Fork

## Overview

This is an enhanced fork of the official AWS HealthOmics MCP Server that adds comprehensive data store management capabilities. It combines the latest upstream features with 28 additional tools for managing HealthOmics Sequence, Variant, Reference, and Annotation stores.

## Why This Fork Exists

In November 2025, AWS announced that Variant and Annotation stores would no longer be available for new HealthOmics customers. However, **existing customers continue to have access** to these critical features for genomic data management.

This fork was created to provide existing customers with a complete MCP server that includes both:
- Latest upstream workflow management features
- Comprehensive data store management tools (developed in PR #1498, which was closed due to the deprecation announcement)

## What's Included

### Upstream Features (Latest)
- ✅ Workflow Management (create, version, list, get)
- ✅ Workflow Execution (start, list, monitor tasks)
- ✅ Workflow Analysis (logs, performance, timeline visualization)
- ✅ Workflow Linting (WDL, CWL validation)
- ✅ Genomics File Search (S3 + HealthOmics stores)
- ✅ ECR Container Tools (clone, permissions, pull-through cache)
- ✅ CodeConnections Management
- ✅ Troubleshooting Tools

### Enhanced Fork Features (28 Additional Tools)

#### Sequence Store Management (6 tools)
- `ListAHOSequenceStores` - List available sequence stores
- `ListAHOReadSets` - List read sets with filtering
- `GetAHOReadSet` - Get detailed read set metadata
- `StartAHOReadSetImportJob` - Import FASTQ/BAM/CRAM from S3
- `GetAHOReadSetImportJob` - Monitor import job status
- `ListAHOReadSetImportJobs` - List import jobs

#### Variant Store Operations (6 tools)
- `ListAHOVariantStores` - List available variant stores
- `GetAHOVariantStore` - Get variant store details
- `SearchAHOVariants` - Search variants by gene/position/type
- `CountAHOVariants` - Count variants matching criteria
- `StartAHOVariantImportJob` - Import VCF files from S3
- `GetAHOVariantImportJob` - Monitor variant import status

#### Reference Store Tools (6 tools)
- `ListAHOReferenceStores` - List available reference stores
- `GetAHOReferenceStore` - Get reference store details
- `ListAHOReferences` - List reference genomes
- `GetAHOReference` - Get reference metadata
- `StartAHOReferenceImportJob` - Import FASTA from S3
- `GetAHOReferenceImportJob` - Monitor reference import status

#### Annotation Store Functions (5 tools)
- `ListAHOAnnotationStores` - List available annotation stores
- `GetAHOAnnotationStore` - Get annotation store details
- `SearchAHOAnnotations` - Search annotations by gene/position
- `StartAHOAnnotationImportJob` - Import annotation files
- `GetAHOAnnotationImportJob` - Monitor annotation import status

#### Data Import & S3 Integration (5 tools)
- `DiscoverAHOGenomicFiles` - Auto-discover genomic files by extension
- `ValidateAHOS3URIFormat` - Validate S3 URI format
- `ListAHOS3BucketContents` - Browse S3 buckets/prefixes
- `GetAHOS3FileMetadata` - Get file size/metadata
- `PrepareAHOImportSources` - Prepare files for HealthOmics import

## Installation

### Prerequisites
- Python 3.10+
- AWS credentials configured
- Access to AWS HealthOmics (with data store features)

### Install from Fork

```bash
# Clone this fork
git clone https://github.com/peterbb148/awslabs-mcp.git
cd awslabs-mcp/src/aws-healthomics-mcp-server

# Install with uv (recommended)
uv pip install -e .

# Or with pip
pip install -e .
```

### Usage with Claude Desktop

Add to your Claude Desktop config (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

```json
{
  "mcpServers": {
    "aws-healthomics-enhanced": {
      "command": "uv",
      "args": [
        "--directory",
        "/path/to/awslabs-mcp/src/aws-healthomics-mcp-server",
        "run",
        "aws-healthomics-mcp-server"
      ],
      "env": {
        "AWS_REGION": "us-east-1",
        "AWS_PROFILE": "your-profile"
      }
    }
  }
}
```

## Complete Workflow Example

This enhanced fork enables end-to-end genomic analysis workflows:

### 1. Data Discovery
```
Use SearchGenomicsFiles to find genomic data across S3 and HealthOmics stores
```

### 2. Data Import
```
Use PrepareAHOImportSources to configure S3 sources
Use StartAHOReadSetImportJob to import FASTQ files
Use StartAHOReferenceImportJob to import reference genomes
Use StartAHOVariantImportJob to import VCF files
```

### 3. Workflow Execution
```
Use CreateAHOWorkflow to define analysis pipeline
Use StartAHORun to execute workflow on imported data
Use ListAHORunTasks to monitor progress
```

### 4. Results Analysis
```
Use SearchAHOVariants to query variant results
Use SearchAHOAnnotations to find gene annotations
Use AnalyzeAHORunPerformance for optimization insights
```

### 5. Monitoring & Troubleshooting
```
Use GetAHORunLogs for execution logs
Use DiagnoseAHORunFailure for failure analysis
Use GenerateAHORunTimeline for visualization
```

## Maintenance & Updates

This fork will be periodically synchronized with the upstream AWS repository to incorporate:
- New workflow features
- Security patches
- Bug fixes
- Additional MCP servers

### Update Process

```bash
# Fetch latest from upstream
git fetch upstream

# Checkout the enhanced fork branch
git checkout feature/healthomics-enhanced-fork

# Merge upstream changes
git merge upstream/main

# Resolve any conflicts and push
git push origin feature/healthomics-enhanced-fork
```

## Branch Structure

- `main` - Mirrors upstream AWS repository
- `feature/healthomics-enhanced-fork` - **Use this branch** - Includes all enhancements
- `feature/healthomics-data-store-enhancement-1421` - Original PR branch (preserved)

## Testing

All enhanced features include comprehensive test coverage:

```bash
# Run tests for data store tools
pytest src/aws-healthomics-mcp-server/tests/test_sequence_store_tools.py
pytest src/aws-healthomics-mcp-server/tests/test_data_import_tools.py

# Run all tests
pytest src/aws-healthomics-mcp-server/tests/
```

## Contributing

Since this is a fork for existing HealthOmics customers:

1. **For upstream features**: Contribute directly to [awslabs/mcp](https://github.com/awslabs/mcp)
2. **For data store enhancements**: Create issues or PRs in this fork
3. **For bugs**: Check if it exists upstream first, then report here if fork-specific

## License

This project maintains the same Apache 2.0 license as the upstream AWS repository. See [LICENSE](LICENSE) for details.

## Acknowledgments

- AWS Labs for the original HealthOmics MCP Server
- AWS HealthOmics team for continued support of data store features for existing customers
- MCP (Model Context Protocol) project by Anthropic

## Support

This is a community-maintained fork. For:
- **AWS HealthOmics service issues**: Contact AWS Support
- **Upstream MCP server issues**: Open issues at [awslabs/mcp](https://github.com/awslabs/mcp)
- **Fork-specific issues**: Open issues in this repository

## Version History

- **February 2026**: Enhanced fork created
  - Merged upstream main (728 commits ahead)
  - Integrated data store management tools
  - Added 28 new tools for comprehensive data management
  
- **October 2025**: Original PR #1498 submitted
  - Developed data store management features
  - Full test coverage implemented
  - Addressed code review feedback

- **November 2025**: AWS announced Variant/Annotation store deprecation for new customers
  - PR marked as stale
  - Continued support confirmed for existing customers

- **January 2026**: PR closed due to inactivity
  - Decision to maintain as enhanced fork for existing customers

## Links

- **This Fork**: https://github.com/peterbb148/awslabs-mcp
- **Upstream**: https://github.com/awslabs/mcp
- **Original PR**: https://github.com/awslabs/mcp/pull/1498
- **AWS HealthOmics**: https://aws.amazon.com/healthomics/

---

**Note**: This enhanced fork is specifically designed for existing AWS HealthOmics customers who have continued access to Sequence, Variant, Reference, and Annotation stores. New customers should use the official upstream version which focuses on workflow management features.
