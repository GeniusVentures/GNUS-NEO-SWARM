# Phase 08: Agentic Memory (GAML v1) - Pattern Map

**Mapped:** 2026-07-23
**Files analyzed:** 23 (14 new, 5 modified, 4 test)
**Analogs found:** 23 / 23

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/memory/CMakeLists.txt` | config | build | `src/reputation/CMakeLists.txt` | exact |
| `src/memory/memory_storage.hpp` | service | file-I/O | `src/reputation/reputation_storage.hpp` | exact |
| `src/memory/memory_storage.cpp` | service | file-I/O | `src/reputation/reputation_storage.cpp` | exact |
| `src/memory/memory_governor.hpp` | service | CRUD | `src/knowledge/knowledge_retrieval.hpp` | role-match |
| `src/memory/memory_governor.cpp` | service | CRUD | `src/knowledge/knowledge_retrieval.cpp` | role-match |
| `src/memory/fact_extraction.hpp` | utility | transform | `src/router/prompt_analyzer.hpp` | role-match |
| `src/memory/fact_extraction.cpp` | utility | transform | `src/router/prompt_analyzer.cpp` | role-match |
| `src/memory/context_mapping.hpp` | utility | transform | `src/knowledge/context_injection.hpp` | role-match |
| `src/memory/context_mapping.cpp` | utility | transform | `src/knowledge/context_injection.cpp` | role-match |
| `src/memory/write_evaluation.hpp` | utility | transform | `src/knowledge/context_injection.hpp` | partial |
| `src/memory/write_evaluation.cpp` | utility | transform | `src/knowledge/knowledge_retrieval.cpp` (scoring) | partial |
| `src/common/types.hpp` (modify) | model | — | self (extend existing enums/structs) | exact |
| `src/common/error.hpp` (modify) | config | — | self (extend Error enum) | exact |
| `src/elm/elm_chain_builder.hpp` (modify) | service | CRUD | self (add Config field) | exact |
| `src/elm/elm_chain_builder.cpp` (modify) | service | CRUD | self (add needs_retrieval set) | exact |
| `src/api/api_server.hpp` (modify) | controller | request-response | self (add unique_ptr members) | exact |
| `src/api/api_server.cpp` (modify) | controller | request-response | self (AugmentPattern + Initialize patterns) | exact |
| `src/CMakeLists.txt` (modify) | config | build | self (add_subdirectory) | exact |
| `test/memory/test_memory_types.cpp` | test | unit | `test/reputation/test_reputation.cpp` | role-match |
| `test/memory/test_memory_storage.cpp` | test | unit (RocksDB) | `test/reputation/test_reputation.cpp` (Storage tests) | exact |
| `test/memory/test_memory_governor.cpp` | test | unit | `test/knowledge/test_knowledge_retrieval.cpp` | role-match |
| `test/memory/test_memory_ingestion.cpp` | test | unit (pipeline) | `test/elm/test_elm.cpp` (MockEngine pattern) | partial |
| `test/CMakeLists.txt` (modify) | config | build | self (neoswarm_test entries) | exact |

## Pattern Assignments

---

### 1. `src/memory/CMakeLists.txt` (config, build)

**Analog:** `src/reputation/CMakeLists.txt` (full file, 23 lines)

**Core library definition pattern** (lines 1-22):
```cmake
add_library(neoswarm_memory STATIC
    memory_storage.cpp
    memory_governor.cpp
    fact_extraction.cpp
    context_mapping.cpp
    write_evaluation.cpp
)

target_include_directories(neoswarm_memory PUBLIC
    $<BUILD_INTERFACE:${PROJECT_ROOT}/src>
    $<INSTALL_INTERFACE:include>
)

target_link_libraries(neoswarm_memory PUBLIC
    neoswarm_common
)

if(TARGET RocksDB::rocksdb)
    target_link_libraries(neoswarm_memory PUBLIC RocksDB::rocksdb)
elseif(TARGET rocksdb)
    target_link_libraries(neoswarm_memory PUBLIC rocksdb)
endif()
```

**Also needs nlohmann_json linking** (pattern from `src/network/CMakeLists.txt`):
```cmake
# After RocksDB block, add:
if(TARGET nlohmann_json::nlohmann_json)
    target_link_libraries(neoswarm_memory PUBLIC nlohmann_json::nlohmann_json)
endif()
```

---

### 2. `src/memory/memory_storage.hpp` (service, file-I/O)

**Analog:** `src/reputation/reputation_storage.hpp` (full file, 94 lines)

**Imports/header guard pattern** (lines 1-16):
```cpp
/**
 * @file       memory_storage.hpp
 * @brief      RocksDB-backed memory object persistence (GAML v1)
 */

#ifndef NEOSWARM_MEMORY_MEMORYSTORAGE_HPP
#define NEOSWARM_MEMORY_MEMORYSTORAGE_HPP

#include "common/error.hpp"
#include "common/types.hpp"
#include <memory>
#include <string>
#include <vector>

namespace sgns::neoswarm::memory
{
```

**Class declaration with Pimpl + Config pattern** (lines 18-91, adapted):
```cpp
    /**
     * @brief Persists CognitiveAsset memory objects to RocksDB.
     *
     * Uses the Pimpl idiom — header has ZERO RocksDB includes.
     * Key format: {entity}/{type}/{timestamp_ns}/{id}
     */
    class MemoryStorage
    {
        public:
        struct Config
        {
            std::string m_dbPath = "./memory.db";
        };

        explicit MemoryStorage(const Config& cfg);
        ~MemoryStorage();

        outcome::result<void> Open();
        void Close();
        bool IsOpen() const { return m_open; }

        outcome::result<void> Put(const CognitiveAsset& obj);
        outcome::result<void> PutBatch(const std::vector<CognitiveAsset>& objects);
        outcome::result<std::vector<CognitiveAsset>> GetByPrefix(
            const std::string& prefix, int maxResults = 10) const;
        outcome::result<CognitiveAsset> Get(const std::string& key) const;

    private:
        struct Impl;
        std::unique_ptr<Impl> m_impl;
        Config m_cfg;
        bool m_open = false;

        static std::string BuildKey(const CognitiveAsset& obj);
        static std::string Serialize(const CognitiveAsset& obj);
        static outcome::result<CognitiveAsset> Deserialize(const std::string& data);
    };

} // namespace sgns::neoswarm::memory

#endif
```

**Key pattern details from analog:**
- `struct Impl` forward-declared in header, defined in .cpp — `src/reputation/reputation_storage.hpp` line 83
- `std::unique_ptr<Impl> m_impl` — line 84
- `bool open_ = false` — line 86 (but use `m_open` per SuperGenius naming convention)
- Static `Serialize`/`Deserialize` — lines 88-89
- Config struct via constructor (follows `KnowledgeRetrieval::Config` pattern from `src/knowledge/knowledge_retrieval.hpp` lines 27-34)

---

### 3. `src/memory/memory_storage.cpp` (service, file-I/O)

**Analog:** `src/reputation/reputation_storage.cpp` (full file, 225 lines)

**Logger pattern** (lines 19-25):
```cpp
#include "memory_storage.hpp"
#include "common/logging.hpp"

#include <rocksdb/db.h>
#include <rocksdb/options.h>
#include <rocksdb/slice.h>
#include <rocksdb/write_batch.h>

#include <nlohmann/json.hpp>

namespace sgns::neoswarm::memory
{
    namespace
    {
        auto StorageLogger()
        {
            return neoswarm::CreateLogger("MemoryStorage");
        }
    } // namespace
```

**Impl struct** (line 67-72, adapted for JSON instead of protobuf):
```cpp
    struct MemoryStorage::Impl
    {
        rocksdb::DB* m_db = nullptr;
        rocksdb::Options m_options;
    };
```

**Constructor** (lines 74-78):
```cpp
    MemoryStorage::MemoryStorage(const Config& cfg)
        : m_impl(std::make_unique<Impl>())
        , m_cfg(cfg)
    {
    }
```

**Destructor** (lines 80-83):
```cpp
    MemoryStorage::~MemoryStorage()
    {
        Close();
    }
```

**Open pattern** (lines 88-100):
```cpp
    outcome::result<void> MemoryStorage::Open()
    {
        m_impl->m_options.create_if_missing = true;
        rocksdb::Status status = rocksdb::DB::Open(m_impl->m_options, m_cfg.m_dbPath, &m_impl->m_db);
        if (!status.ok())
        {
            StorageLogger()->error("MemoryStorage open failed: {}", status.ToString());
            return outcome::failure(Error::StorageError);
        }
        StorageLogger()->info("MemoryStorage opened: {}", m_cfg.m_dbPath);
        m_open = true;
        return outcome::success();
    }
```

**Close pattern** (lines 105-113):
```cpp
    void MemoryStorage::Close()
    {
        if (m_impl && m_impl->m_db)
        {
            delete m_impl->m_db;
            m_impl->m_db = nullptr;
        }
        m_open = false;
    }
```

**Put pattern** (lines 118-134, adapted for CognitiveAsset):
```cpp
    outcome::result<void> MemoryStorage::Put(const CognitiveAsset& obj)
    {
        if (!m_open)
            return outcome::failure(Error::StorageError);

        std::string key = BuildKey(obj);
        std::string val = Serialize(obj);
        rocksdb::WriteOptions opts;
        opts.sync = true;
        auto status = m_impl->m_db->Put(opts, key, val);
        if (!status.ok())
            return outcome::failure(Error::StorageError);

        return outcome::success();
    }
```

**Get pattern** (lines 139-156, adapted with IsNotFound check):
```cpp
    outcome::result<CognitiveAsset> MemoryStorage::Get(const std::string& key) const
    {
        if (!m_open)
            return outcome::failure(Error::StorageError);

        std::string val;
        rocksdb::Status status = m_impl->m_db->Get(rocksdb::ReadOptions(), key, &val);
        if (status.IsNotFound())
            return outcome::failure(Error::MemoryNotFound);
        if (!status.ok())
            return outcome::failure(Error::StorageError);

        return Deserialize(val);
    }
```

**GetByPrefix (iterator) pattern** (from `reputation_storage.cpp` lines 180-199, adapted with prefix seek):
```cpp
    outcome::result<std::vector<CognitiveAsset>> MemoryStorage::GetByPrefix(
        const std::string& prefix, int maxResults) const
    {
        if (!m_open)
            return outcome::failure(Error::StorageError);

        std::vector<CognitiveAsset> results;
        auto* it = m_impl->m_db->NewIterator(rocksdb::ReadOptions());

        for (it->Seek(prefix);
             it->Valid() &&
             it->key().ToString().compare(0, prefix.size(), prefix) == 0 &&  // C++17: not starts_with
             static_cast<int>(results.size()) < maxResults;
             it->Next())
        {
            auto obj = Deserialize(it->value().ToString());
            if (obj.has_value())
                results.push_back(std::move(obj.value()));
        }
        delete it;
        return outcome::success(std::move(results));
    }
```

**PutBatch pattern** (lines 204-223):
```cpp
    outcome::result<void> MemoryStorage::PutBatch(const std::vector<CognitiveAsset>& objects)
    {
        if (!m_open)
            return outcome::failure(Error::StorageError);

        rocksdb::WriteBatch batch;
        for (const auto& obj : objects)
        {
            batch.Put(BuildKey(obj), Serialize(obj));
        }
        rocksdb::WriteOptions opts;
        opts.sync = true;
        auto status = m_impl->m_db->Write(opts, &batch);
        if (!status.ok())
            return outcome::failure(Error::StorageError);

        return outcome::success();
    }
```

**BuildKey pattern** (D-14: `{entity}/{type}/{timestamp_ns}/{id}`):
```cpp
    std::string MemoryStorage::BuildKey(const CognitiveAsset& obj)
    {
        // Sanitize entity — replace '/' with '_' (Pitfall 2)
        std::string safeEntity = obj.m_entity;
        for (auto& c : safeEntity)
            if (c == '/') c = '_';

        return safeEntity + "/" +
               std::to_string(static_cast<int>(obj.m_type)) + "/" +
               std::to_string(obj.m_timestamp) + "/" +
               obj.m_id;
    }
```

**JSON Serialization** (pattern from RESEARCH.md verified against nlohmann/json usage in `src/genius_elm_chat_completions.cpp:115`, `src/main.cpp:98`):
```cpp
    std::string MemoryStorage::Serialize(const CognitiveAsset& obj)
    {
        nlohmann::json j;
        j["id"] = obj.m_id;
        j["entity"] = obj.m_entity;
        j["type"] = static_cast<int>(obj.m_type);
        j["payload"] = obj.m_payload;
        j["timestamp"] = obj.m_timestamp;
        j["source_node"] = obj.m_sourceNode;
        j["confidence"] = obj.m_confidence;
        j["provenance"] = obj.m_provenance;
        j["trust_class"] = static_cast<int>(obj.m_trustClass);
        return j.dump();
    }

    outcome::result<CognitiveAsset> MemoryStorage::Deserialize(const std::string& data)
    {
        try
        {
            auto j = nlohmann::json::parse(data);
            CognitiveAsset obj;
            obj.m_id = j.value("id", "");
            obj.m_entity = j.value("entity", "");
            obj.m_type = static_cast<MemoryObjectType>(j.value("type", 0));
            obj.m_payload = j.value("payload", nlohmann::json::object());
            obj.m_timestamp = j.value("timestamp", int64_t(0));
            obj.m_sourceNode = j.value("source_node", "");
            obj.m_confidence = j.value("confidence", 0.0f);
            obj.m_provenance = j.value("provenance", 0.0f);
            obj.m_trustClass = static_cast<TrustClass>(j.value("trust_class", 0));
            return outcome::success(std::move(obj));
        }
        catch (const nlohmann::json::exception& e)
        {
            StorageLogger()->error("JSON deserialization failed: {}", e.what());
            return outcome::failure(Error::StorageError);
        }
    }
```

---

### 4. `src/memory/memory_governor.hpp` (service, CRUD)

**Analog:** `src/knowledge/knowledge_retrieval.hpp` (full file, 83 lines)

**Imports/pattern** (lines 1-15):
```cpp
/**
 * @file       memory_governor.hpp
 * @brief      Standalone memory retrieval orchestrator (GAML v1)
 */

#ifndef NEOSWARM_MEMORY_MEMORYGOVERNOR_HPP
#define NEOSWARM_MEMORY_MEMORYGOVERNOR_HPP

#include "common/error.hpp"
#include "common/types.hpp"
#include <memory>
#include <string>

namespace sgns::neoswarm::memory
```

**Config struct + class declaration** (lines 27-80, adapted from KnowledgeRetrieval):
```cpp
{
    // Forward declaration
    class MemoryStorage;

    /**
     * @brief Retrieves relevant memory objects using heuristic entity-match +
     *        recency + confidence ranking (Phase 8, ML-assisted deferred).
     *
     * Does NOT implement IELM — standalone orchestration component.
     */
    class MemoryGovernor
    {
        public:
        struct Config
        {
            int m_topK = 10;                  ///< max results returned
            float m_minConfidence = 0.3f;      ///< minimum confidence to include
            int64_t m_maxAgeNs = 86400LL * 1000000000LL; ///< 24h default
            bool m_enabled = true;
        };

        explicit MemoryGovernor(Config cfg, MemoryStorage* storage);
        ~MemoryGovernor();

        /// @return True if governor is ready to serve queries.
        bool IsReady() const { return m_storage != nullptr && m_cfg.m_enabled; }

        /**
         * @brief Retrieve memory context for a task.
         * @param task   Incoming task (used for entity extraction).
         * @param chain  Execution chain (used for context building).
         * @return       MemoryContext with facts + policies, or empty context on no results.
         */
        MemoryContext Retrieve(const Task& task, const ExecutionChain& chain) const;

        private:
        Config m_cfg;
        MemoryStorage* m_storage;  ///< non-owning — owned by ApiServer

        std::string ExtractEntity(const std::string& prompt) const;
        std::vector<CognitiveAsset> FilterAndRank(
            const std::vector<CognitiveAsset>& candidates) const;
    };

} // namespace sgns::neoswarm::memory

#endif
```

---

### 5. `src/memory/memory_governor.cpp` (service, CRUD)

**Analog:** `src/knowledge/knowledge_retrieval.cpp` (lines 158-191, Retrieve method) + `src/reputation/reputation_crdt.cpp` (mutex pattern for thread safety)

**Logger + constructor pattern** (from `knowledge_retrieval.cpp` lines 18-45):
```cpp
#include "memory_governor.hpp"
#include "memory_storage.hpp"
#include "common/logging.hpp"

#include <algorithm>
#include <regex>

namespace sgns::neoswarm::memory
{
    namespace
    {
        auto GovernorLogger()
        {
            return neoswarm::CreateLogger("MemoryGovernor");
        }
    } // namespace

    MemoryGovernor::MemoryGovernor(Config cfg, MemoryStorage* storage)
        : m_cfg(std::move(cfg))
        , m_storage(storage)
    {
    }

    MemoryGovernor::~MemoryGovernor() = default;
```

**Entity extraction pattern** (from `src/router/prompt_analyzer.cpp` lines 142-160, keyword matching):
```cpp
    std::string MemoryGovernor::ExtractEntity(const std::string& prompt) const
    {
        // v1: simple first-line heuristic + keyword extraction
        // ML-assisted deferred to post-Phase 8
        std::string lower = prompt;
        std::transform(lower.begin(), lower.end(), lower.begin(),
                       [](unsigned char c) { return std::tolower(c); });

        // Try first meaningful word after common prefixes
        static const std::vector<std::string> kPrefixes = {
            "explain", "what is", "tell me about", "describe", "define",
            "how does", "why is", "who is", "where is", "when did"
        };

        for (const auto& prefix : kPrefixes)
        {
            auto pos = lower.find(prefix);
            if (pos != std::string::npos && pos + prefix.size() < lower.size())
            {
                std::string rest = prompt.substr(pos + prefix.size());
                // Take first 3 words as entity
                std::istringstream iss(rest);
                std::string word, entity;
                int count = 0;
                while (iss >> word && count < 3)
                {
                    if (!entity.empty()) entity += "_";
                    entity += word;
                    ++count;
                }
                return entity;
            }
        }
        // Fallback: entire prompt (truncated)
        return prompt.substr(0, 60);
    }
```

**FilterAndRank pattern** (from `knowledge_retrieval.cpp` lines 167-179, scoring + sorting):
```cpp
    std::vector<CognitiveAsset> MemoryGovernor::FilterAndRank(
        const std::vector<CognitiveAsset>& candidates) const
    {
        std::vector<std::pair<float, size_t>> scored;
        scored.reserve(candidates.size());

        int64_t now = std::chrono::steady_clock::now().time_since_epoch().count();
        int64_t cutoff = now - m_cfg.m_maxAgeNs;

        for (size_t i = 0; i < candidates.size(); ++i)
        {
            const auto& obj = candidates[i];
            if (obj.m_confidence < m_cfg.m_minConfidence)
                continue;
            if (obj.m_timestamp < cutoff)
                continue;

            // Recency-weighted confidence: newer = bonus
            float ageRatio = static_cast<float>(obj.m_timestamp - cutoff) /
                             static_cast<float>(m_cfg.m_maxAgeNs);
            float score = obj.m_confidence * (0.7f + 0.3f * ageRatio);
            scored.push_back({score, i});
        }

        std::sort(scored.begin(), scored.end(),
                  [](const auto& a, const auto& b) { return a.first > b.first; });

        std::vector<CognitiveAsset> results;
        for (size_t i = 0; i < scored.size() && i < static_cast<size_t>(m_cfg.m_topK); ++i)
        {
            results.push_back(candidates[scored[i].second]);
        }
        return results;
    }
```

**Retrieve method** (from `knowledge_retrieval.cpp` lines 158-191, Retrieve + scoring pattern):
```cpp
    MemoryContext MemoryGovernor::Retrieve(const Task& task, const ExecutionChain& chain) const
    {
        MemoryContext ctx;
        if (!IsReady() || !m_storage || !m_storage->IsOpen())
        {
            GovernorLogger()->debug("MemoryGovernor not ready — returning empty context");
            return ctx;
        }

        std::string entity = ExtractEntity(task.m_prompt);
        GovernorLogger()->debug("Extracted entity: '{}'", entity);

        // Retrieve by entity prefix scan
        auto factsRes = m_storage->GetByPrefix(entity + "/" +
            std::to_string(static_cast<int>(MemoryObjectType::fact)) + "/", m_cfg.m_topK * 2);
        auto policiesRes = m_storage->GetByPrefix(entity + "/" +
            std::to_string(static_cast<int>(MemoryObjectType::policy)) + "/", m_cfg.m_topK * 2);

        // Filter and rank
        if (factsRes.has_value())
            ctx.m_facts = FilterAndRank(factsRes.value());
        if (policiesRes.has_value())
            ctx.m_policies = FilterAndRank(policiesRes.value());

        GovernorLogger()->info("Retrieved {} facts, {} policies for entity '{}'",
                               ctx.m_facts.size(), ctx.m_policies.size(), entity);
        return ctx;
    }

} // namespace sgns::neoswarm::memory
```

---

### 6. `src/memory/fact_extraction.hpp` (utility, transform)

**Analog:** `src/router/prompt_analyzer.hpp` (lines 20-27, single-analyze pattern) + `src/knowledge/context_injection.hpp` (Config pattern)

```cpp
/**
 * @file       fact_extraction.hpp
 * @brief      Stage 1: Regex-based fact extraction from ELM output (GAML v1)
 */

#ifndef NEOSWARM_MEMORY_FACTEXTRACTION_HPP
#define NEOSWARM_MEMORY_FACTEXTRACTION_HPP

#include "common/error.hpp"
#include "common/types.hpp"
#include <string>
#include <vector>

namespace sgns::neoswarm::memory
{
    /**
     * @brief Extracts potential MemoryObject facts from inference output text
     *        using regex patterns (v1 — ML-assisted deferred).
     */
    class FactExtraction
    {
        public:
        struct Config
        {
            float m_minConfidence = 0.3f;    ///< confidence floor for extracted facts
            int m_maxFacts = 20;             ///< cap on extracted facts per response
        };

        explicit FactExtraction(Config cfg = {});
        ~FactExtraction() = default;

        /**
         * @brief Extract MemoryObject facts from inference output text.
         * @param text   Raw ELM output text.
         * @param task   Original task (for source tracking).
         * @return       Vector of facts (type=facts) or error.
         */
        outcome::result<std::vector<CognitiveAsset>> Extract(
            const std::string& text, const Task& task) const;

        private:
        Config m_cfg;

        bool IsDeclarativeSentence(const std::string& sentence) const;
        float ScoreFactConfidence(const std::string& sentence) const;
    };

} // namespace sgns::neoswarm::memory

#endif
```

---

### 7. `src/memory/fact_extraction.cpp` (utility, transform)

**Analog:** `src/router/prompt_analyzer.cpp` lines 79-85 (std::regex pattern), lines 142-160 (keyword matching), lines 216-228 (Analyze method — feature extraction pattern)

**Logger + constructor** (from prompt_analyzer.cpp — though prompt_analyzer doesn't have logging; add lightweight logger):
```cpp
#include "fact_extraction.hpp"
#include "common/logging.hpp"

#include <regex>
#include <sstream>
#include <algorithm>

namespace sgns::neoswarm::memory
{
    namespace
    {
        auto ExtractionLogger()
        {
            return neoswarm::CreateLogger("FactExtraction");
        }
    } // namespace

    FactExtraction::FactExtraction(Config cfg)
        : m_cfg(std::move(cfg))
    {
    }
```

**Extract method** (pattern from `prompt_analyzer.cpp` lines 216-228 — multi-stage analysis):
```cpp
    outcome::result<std::vector<CognitiveAsset>> FactExtraction::Extract(
        const std::string& text, const Task& task) const
    {
        std::vector<CognitiveAsset> facts;

        // Split by sentence boundaries
        static const std::regex kSentencePattern(R"(([^.!?]+[.!?]))");
        auto begin = std::sregex_iterator(text.begin(), text.end(), kSentencePattern);
        auto end = std::sregex_iterator();

        int64_t now = std::chrono::steady_clock::now().time_since_epoch().count();

        for (auto it = begin; it != end && static_cast<int>(facts.size()) < m_cfg.m_maxFacts; ++it)
        {
            std::string sentence = it->str();
            // Trim whitespace
            sentence.erase(0, sentence.find_first_not_of(" \t\n\r"));
            sentence.erase(sentence.find_last_not_of(" \t\n\r") + 1);

            if (sentence.empty() || sentence.size() < 10) continue;
            if (!IsDeclarativeSentence(sentence)) continue;

            float confidence = ScoreFactConfidence(sentence);
            if (confidence < m_cfg.m_minConfidence) continue;

            CognitiveAsset fact;
            fact.m_id = "mem-" + std::to_string(now) + "-" + std::to_string(facts.size());
            fact.m_entity = ""; // set by ContextMapping
            fact.m_type = MemoryObjectType::fact;
            fact.m_payload = nlohmann::json::object({
                {"content", sentence},
                {"source_task_id", task.m_id}
            });
            fact.m_timestamp = now;
            fact.m_sourceNode = task.m_nodeId;
            fact.m_confidence = confidence;
            fact.m_provenance = 0.5f;
            fact.m_trustClass = TrustClass::unverified;

            facts.push_back(std::move(fact));
        }

        ExtractionLogger()->debug("Extracted {} facts from {} chars of text",
                                  facts.size(), text.size());
        return outcome::success(std::move(facts));
    }

    bool FactExtraction::IsDeclarativeSentence(const std::string& sentence) const
    {
        // Skip questions, imperatives, fragments
        if (sentence.find('?') != std::string::npos) return false;
        if (sentence.find("please") != std::string::npos) return false;
        if (sentence.find("!") != std::string::npos) return false;
        // Must have a subject-verb pattern (simple heuristic)
        static const std::regex kDeclarative(R"(\b(is|are|was|were|has|have|can|will|should|may|might|must|means)\b)",
                                             std::regex::icase);
        return std::regex_search(sentence, kDeclarative);
    }

    float FactExtraction::ScoreFactConfidence(const std::string& sentence) const
    {
        // v1: simple heuristics — length, specificity keywords
        float score = 0.3f;

        // Longer sentences tend to be more factual (but not too long)
        size_t len = sentence.size();
        if (len > 30 && len < 500) score += 0.2f;

        // Specificity keywords
        static const std::vector<std::string> kSpecificWords = {
            "is", "are", "was", "means", "defined", "approximately",
            "characterized", "consists", "contains", "includes", "refers",
            "located", "found", "known", "discovered", "measured"
        };
        for (const auto& word : kSpecificWords)
        {
            if (sentence.find(word) != std::string::npos)
            {
                score += 0.05f;
            }
        }

        // Citations/references boost
        static const std::regex kCitation(R"(\[(\d+)\])");
        if (std::regex_search(sentence, kCitation)) score += 0.1f;

        return std::min(score, 1.0f);
    }

} // namespace sgns::neoswarm::memory
```

---

### 8. `src/memory/context_mapping.hpp` (utility, transform)

**Analog:** `src/knowledge/context_injection.hpp` (lines 19-49, single-method class with Config)

```cpp
/**
 * @file       context_mapping.hpp
 * @brief      Stage 2: Entity assignment + provenance mapping (GAML v1)
 */

#ifndef NEOSWARM_MEMORY_CONTEXTMAPPING_HPP
#define NEOSWARM_MEMORY_CONTEXTMAPPING_HPP

#include "common/types.hpp"
#include <string>
#include <vector>

namespace sgns::neoswarm::memory
{
    /**
     * @brief Assigns entity, provenance, and trust class to extracted facts.
     */
    class ContextMapping
    {
        public:
        struct Config
        {
            float m_defaultProvenance = 0.5f;
        };

        explicit ContextMapping(Config cfg = {});
        ~ContextMapping() = default;

        /**
         * @brief Map extracted facts with context metadata.
         * @param facts  Facts from Stage 1 (FactExtraction).
         * @param task   Original task for entity extraction.
         * @return       Facts with m_entity, m_provenance, m_trustClass set.
         */
        std::vector<CognitiveAsset> Map(std::vector<CognitiveAsset> facts,
                                        const Task& task) const;

        private:
        Config m_cfg;
        std::string ExtractEntity(const std::string& prompt) const;
    };

} // namespace sgns::neoswarm::memory

#endif
```

---

### 9. `src/memory/context_mapping.cpp` (utility, transform)

**Analog:** `src/knowledge/context_injection.cpp` (full file, 65 lines) — simple class, single public method

```cpp
/**
 * @file       context_mapping.cpp
 * @brief      ContextMapping implementation — entity assignment
 */

#include "context_mapping.hpp"
#include "common/logging.hpp"

#include <algorithm>
#include <sstream>

namespace sgns::neoswarm::memory
{
    namespace
    {
        auto MappingLogger()
        {
            return neoswarm::CreateLogger("ContextMapping");
        }
    } // namespace

    ContextMapping::ContextMapping(Config cfg)
        : m_cfg(std::move(cfg))
    {
    }

    std::vector<CognitiveAsset> ContextMapping::Map(std::vector<CognitiveAsset> facts,
                                                     const Task& task) const
    {
        std::string entity = ExtractEntity(task.m_prompt);
        for (auto& fact : facts)
        {
            fact.m_entity = entity;
            fact.m_provenance = m_cfg.m_defaultProvenance;
            fact.m_trustClass = TrustClass::unverified; // D-09: privacy stub
        }
        MappingLogger()->debug("Mapped {} facts to entity '{}'", facts.size(), entity);
        return facts;
    }

    std::string ContextMapping::ExtractEntity(const std::string& prompt) const
    {
        // Simple: take first 80 chars, replace spaces with underscores
        std::string entity = prompt.substr(0, 80);
        // Remove non-alpha except spaces
        entity.erase(std::remove_if(entity.begin(), entity.end(),
            [](unsigned char c) { return !std::isalnum(c) && c != ' '; }), entity.end());
        for (auto& c : entity)
            if (c == ' ') c = '_';
        if (entity.empty()) entity = "general";
        return entity;
    }

} // namespace sgns::neoswarm::memory
```

---

### 10. `src/memory/write_evaluation.hpp` (utility, transform)

**Analog:** `src/knowledge/context_injection.hpp` (lines 19-49 — single-method class with Config)

```cpp
/**
 * @file       write_evaluation.hpp
 * @brief      Stage 3: Novelty/utility scoring + write-filtering (GAML v1)
 */

#ifndef NEOSWARM_MEMORY_WRITEEVALUATION_HPP
#define NEOSWARM_MEMORY_WRITEEVALUATION_HPP

#include "common/error.hpp"
#include "common/types.hpp"
#include <string>
#include <vector>

namespace sgns::neoswarm::memory
{
    // Forward declaration
    class MemoryStorage;

    /**
     * @brief Scores facts for novelty and utility, keeping only those
     *        above thresholds for persistence.
     */
    class WriteEvaluation
    {
        public:
        struct Config
        {
            float m_noveltyThreshold = 0.3f;   ///< minimum novelty score to keep
            float m_utilityThreshold = 0.2f;   ///< minimum utility score to keep
            float m_overallThreshold = 0.4f;   ///< minimum combined score
            bool m_enabled = true;
        };

        explicit WriteEvaluation(Config cfg = {});
        ~WriteEvaluation() = default;

        /**
         * @brief Evaluate and filter facts, persisting accepted ones.
         * @param facts    Facts to evaluate.
         * @param storage  Memory storage for novelty check.
         * @return         Facts that passed the write filter, or error.
         */
        outcome::result<std::vector<CognitiveAsset>> Evaluate(
            std::vector<CognitiveAsset> facts, MemoryStorage* storage) const;

        private:
        Config m_cfg;

        float ScoreNovelty(const CognitiveAsset& fact, MemoryStorage* storage) const;
        float ScoreUtility(const CognitiveAsset& fact) const;
    };

} // namespace sgns::neoswarm::memory

#endif
```

---

### 11. `src/memory/write_evaluation.cpp` (utility, transform)

**Analog:** `src/knowledge/knowledge_retrieval.cpp` lines 155-191 (scoring + filtering pattern)

```cpp
/**
 * @file       write_evaluation.cpp
 * @brief      WriteEvaluation implementation — novelty/utility scoring
 */

#include "write_evaluation.hpp"
#include "memory_storage.hpp"
#include "common/logging.hpp"

#include <algorithm>

namespace sgns::neoswarm::memory
{
    namespace
    {
        auto EvalLogger()
        {
            return neoswarm::CreateLogger("WriteEvaluation");
        }
    } // namespace

    WriteEvaluation::WriteEvaluation(Config cfg)
        : m_cfg(std::move(cfg))
    {
    }

    outcome::result<std::vector<CognitiveAsset>> WriteEvaluation::Evaluate(
        std::vector<CognitiveAsset> facts, MemoryStorage* storage) const
    {
        if (!m_cfg.m_enabled) return outcome::success(std::move(facts));

        std::vector<CognitiveAsset> accepted;
        accepted.reserve(facts.size());

        for (auto& fact : facts)
        {
            float novelty = ScoreNovelty(fact, storage);
            float utility = ScoreUtility(fact);

            if (novelty < m_cfg.m_noveltyThreshold) continue;
            if (utility < m_cfg.m_utilityThreshold) continue;

            float overall = (novelty + utility) / 2.0f;
            if (overall < m_cfg.m_overallThreshold) continue;

            fact.m_confidence = overall; // update confidence with evaluation score
            accepted.push_back(std::move(fact));
        }

        EvalLogger()->debug("Write evaluation: {} accepted / {} total",
                            accepted.size(), facts.size());
        return outcome::success(std::move(accepted));
    }

    float WriteEvaluation::ScoreNovelty(const CognitiveAsset& fact, MemoryStorage* storage) const
    {
        // v1: simple existence check — if similar entity+type exists, lower novelty
        if (!storage || !storage->IsOpen()) return 0.5f;

        std::string prefix = fact.m_entity + "/" +
            std::to_string(static_cast<int>(fact.m_type)) + "/";
        auto existing = storage->GetByPrefix(prefix, 1);
        if (!existing.has_value() || existing.value().empty()) return 0.8f; // nothing similar = novel

        return 0.2f; // similar exists = less novel
    }

    float WriteEvaluation::ScoreUtility(const CognitiveAsset& fact) const
    {
        // v1: length-based + keyword heuristic
        float score = 0.3f;
        if (!fact.m_payload.contains("content")) return score;

        std::string content = fact.m_payload["content"].get<std::string>();
        size_t len = content.size();

        // Medium-length facts are most useful (not too short, not a wall of text)
        if (len > 50 && len < 300) score += 0.3f;
        else if (len >= 300 && len < 800) score += 0.1f;

        // Specificity keywords (shared from FactExtraction pattern)
        static const std::vector<std::string> kUsefulWords = {
            "is", "means", "defined", "approximately", "measured",
            "discovered", "introduced", "published", "synthesized"
        };
        for (const auto& word : kUsefulWords)
        {
            if (content.find(word) != std::string::npos)
            {
                score += 0.05f;
            }
        }

        return std::min(score, 1.0f);
    }

} // namespace sgns::neoswarm::memory
```

---

### 12. `src/common/types.hpp` (modify — model)

**Analog:** Self, extend with new enums and structs following the existing patterns for `ELMRole`, `KnowledgeFact`, `ELMContext`, `ExecutionChain`.

**Additions to insert after line 55** (after `ELMRole` enum, before `Task` struct):

```cpp
    // -----------------------------------------------------------------------
    // Memory object types (GAML v1 — Phase 8)
    // -----------------------------------------------------------------------
    enum class MemoryObjectType : uint8_t
    {
        bridge_block = 0,       ///< Memory bridge block
        fact = 1,               ///< Declarative fact
        policy = 2,             ///< Behavioral policy / rule
        event = 3,              ///< Temporal event record
        tenant_operational = 4  ///< Tenant operational data
    };

    enum class TrustClass : uint8_t
    {
        unverified = 0,     ///< Default privacy stub (D-09)
        verified = 1,       ///< Fact-validated
        premium = 2,        ///< Premium tier
        replica = 3         ///< Replicated from remote
    };
```

**Insert after `KnowledgeFact` struct** (after line 151):
```cpp
    // -----------------------------------------------------------------------
    // GAML v1 Memory Object (Phase 8 — local-only)
    // -----------------------------------------------------------------------
    struct CognitiveAsset
    {
        std::string m_id;                  ///< UUID (D-01)
        std::string m_entity;              ///< entity domain (e.g. "quantum_mechanics")
        MemoryObjectType m_type = MemoryObjectType::fact;
        nlohmann::json m_payload;          ///< variable-format payload (D-01)
        int64_t m_timestamp = 0;           ///< nanoseconds since epoch (D-11, CRDT-ready)
        std::string m_sourceNode;          ///< originating NodeID (D-11, CRDT-ready)
        float m_confidence = 0.0f;         ///< extraction/inference confidence
        float m_provenance = 0.0f;         ///< provenance score
        TrustClass m_trustClass = TrustClass::unverified;  ///< trust classification (D-09)
    };
```

**Modify `ExecutionChain`** (after line 176, add `m_needsRetrieval`):
```cpp
    struct ExecutionChain
    {
        std::vector<ChainStep> m_steps;
        std::string m_reasoning;          ///< why this chain was chosen
        float m_chainConfidence = 0.0f;   ///< builder's confidence in this chain
        bool m_needsRetrieval = false;    ///< D-16: set by ELMChainBuilder for complex/grounding tasks
    };
```

**Modify `ELMContext`** (after line 164):
```cpp
    struct ELMContext
    {
        std::string m_originalTask;
        std::vector<std::pair<ELMRole, float>> m_stepConfidences;
        std::vector<KnowledgeFact> m_groundingFacts;
        std::vector<CognitiveAsset> m_memoryFacts;    ///< D-17: facts from MemoryGovernor
        std::vector<CognitiveAsset> m_memoryPolicies;  ///< D-17: policies from MemoryGovernor
    };
```

**Add `MemoryContext` struct** (before closing `} // namespace`):
```cpp
    // -----------------------------------------------------------------------
    // Memory context returned by MemoryGovernor (GAML v1 — Phase 8)
    // -----------------------------------------------------------------------
    struct MemoryContext
    {
        std::vector<CognitiveAsset> m_facts;
        std::vector<CognitiveAsset> m_policies;
    };
```

**Also add to header includes** (line 9, add `#include <nlohmann/json_fwd.hpp>` or forward-declare — but since types.hpp is widely included, prefer adding `<nlohmann/json.hpp>` include to types.hpp. Check if nlohmann/json.hpp is already transitively included... Actually, since `CognitiveAsset` has `nlohmann::json m_payload`, types.hpp MUST include `<nlohmann/json.hpp>`. This is the canonical pattern used throughout the project.):
```cpp
// Add to includes (before the namespace):
#include <nlohmann/json.hpp>
```

---

### 13. `src/common/error.hpp` (modify — config)

**Analog:** Self, extend `Error` enum (lines 18-44).

**Add new error codes** after line 36 (`KnowledgeUnavailable = 11`):
```cpp
        // Memory (Phase 8 — GAML v1)
        MemoryNotFound = 18,          ///< D-20: requested memory object not found
        MemoryUnavailable = 19,       ///< storage offline but not fatal
        MemoryIngestionFailed = 20,   ///< failed write evaluation
```

---

### 14. `src/elm/elm_chain_builder.hpp` (modify — service)

**Analog:** Self (lines 25-31), add Config field for memory retrieval thresholds.

**Add to Config struct** (after line 31):
```cpp
            // Phase 8: Memory retrieval thresholds
            float memory_retrieval_complexity_threshold_ = 3.0f;  ///< complexity above which memory is fetched
            bool enable_memory_retrieval_ = true;                  ///< D-16: enable needs_retrieval flagging
```

---

### 15. `src/elm/elm_chain_builder.cpp` (modify — service)

**Analog:** Self (lines 36-98), add `m_needsRetrieval` set at the end of `Build()`.

**Add after line 93** (after `chain.m_chainConfidence = decision.confidence_;`):
```cpp
        // Phase 8 (D-16): Set needs_retrieval for complex or grounding tasks
        if (m_cfg.enable_memory_retrieval_)
        {
            chain.m_needsRetrieval =
                (features.complexity_ >= m_cfg.memory_retrieval_complexity_threshold_) ||
                features.has_grounding_request_;
        }
```

---

### 16. `src/api/api_server.hpp` (modify — controller)

**Analog:** Self (lines 118-128), add memory member variables following existing `unique_ptr` pattern.

**Add includes** (after line 14, before `#include "network/p2p_node.hpp"`):
```cpp
#include "memory/memory_governor.hpp"
#include "memory/memory_storage.hpp"
```

**Add Config fields** (after line 65, in `Config` struct):
```cpp
            std::string m_memoryDbPath = "./memory.db"; ///< Phase 8: path to memory RocksDB
            bool m_enableMemory = true;                  ///< Phase 8: enable agentic memory
```

**Add member variables** (after line 128, before `m_sgClient`):
```cpp
        std::unique_ptr<memory::MemoryStorage> m_memoryStorage;   // Phase 8
        std::unique_ptr<memory::MemoryGovernor> m_memoryGovernor; // Phase 8
```

**Add private method declarations** (after line 138):
```cpp
        void IngestMemory(const InferenceResponse& resp, const Task& task);
```

---

### 17. `src/api/api_server.cpp` (modify — controller)

**Analog:** Self lines 104-116 (storage initialization in Initialize) + lines 204-217 (AugmentPrompt knowledge injection)

**Add to `Initialize()` method** (after line 119, before `ServerLogger()->info(...)` at line 122):
```cpp
        // 8. Memory (Phase 8 — GAML v1)
        if (m_cfg.m_enableMemory)
        {
            memory::MemoryStorage::Config memStorageCfg;
            memStorageCfg.m_dbPath = m_cfg.m_memoryDbPath;
            m_memoryStorage = std::make_unique<memory::MemoryStorage>(memStorageCfg);
            auto memRes = m_memoryStorage->Open();
            if (!memRes.has_value())
            {
                ServerLogger()->warn("Memory storage open failed — memory disabled (D-20: not fatal)");
                m_memoryStorage.reset();
            }
            else
            {
                memory::MemoryGovernor::Config govCfg;
                m_memoryGovernor = std::make_unique<memory::MemoryGovernor>(govCfg, m_memoryStorage.get());
                ServerLogger()->info("MemoryGovernor initialized");
            }
        }
```

**Add to `Stop()` method** (after line 480, before `m_repStorage->Close()`):
```cpp
        if (m_memoryStorage)
            m_memoryStorage->Close();
```

**Modify `Process()` method** (between route decision and switch statement, after line 446):
```cpp
        // Phase 8 (D-17): Memory retrieval for complex/grounding tasks
        // Note: When ELMChainBuilder is active, m_needsRetrieval is set there.
        //       When not (Phase 7 gap), set inline from PromptFeatures.
        ExecutionChain chain; // When chain builder is wired, use its output instead
        {
            router::PromptAnalyzer analyzer;
            auto features = analyzer.Analyze(t.m_prompt);
            chain.m_needsRetrieval =
                (features.complexity_ >= 3.0f) || features.has_grounding_request_;
        }
```

**Add `IngestMemory()` method** (new, adapted from `AugmentPrompt` pattern lines 204-217 + `UpdateReputation` pattern):
```cpp
    // -----------------------------------------------------------------------
    // IngestMemory — Post-inference ingestion pipeline (Phase 8)
    // -----------------------------------------------------------------------
    void ApiServer::IngestMemory(const InferenceResponse& resp, const Task& task)
    {
        if (!m_memoryGovernor || !m_memoryStorage || !m_memoryStorage->IsOpen())
            return;

        // Stage 1: Fact extraction
        memory::FactExtraction extractor;
        auto extractedRes = extractor.Extract(resp.m_output, task);
        if (!extractedRes.has_value() || extractedRes.value().empty())
            return;

        // Stage 2: Context mapping
        memory::ContextMapping mapper;
        auto mapped = mapper.Map(std::move(extractedRes.value()), task);

        // Stage 3: Write evaluation + persist
        memory::WriteEvaluation evaluator;
        auto acceptedRes = evaluator.Evaluate(std::move(mapped), m_memoryStorage.get());

        if (acceptedRes.has_value() && !acceptedRes.value().empty())
        {
            auto putRes = m_memoryStorage->PutBatch(acceptedRes.value());
            if (!putRes.has_value())
            {
                ServerLogger()->warn("Memory ingestion PutBatch failed");
            }
            else
            {
                ServerLogger()->debug("Memory ingested {} facts", acceptedRes.value().size());
            }
        }
    }
```

**Call IngestMemory at end of RunSingleNode** (after line 275, before `return`):
```cpp
        IngestMemory(resp, task);
```

**Same call in RunSpecialist** (after line 335, before `return`):
```cpp
        IngestMemory(resp, task);
```

**Same call in RunSwarm** (after line 414, before `return`):
```cpp
        IngestMemory(resp, task);
```

---

### 18. `src/CMakeLists.txt` (modify — config)

**Analog:** Self (lines 1-12), add one line after existing `add_subdirectory` entries.

**Add after line 10** (after `add_subdirectory(... elm ...)`):
```cmake
add_subdirectory(${CMAKE_CURRENT_LIST_DIR}/memory ${CMAKE_CURRENT_BINARY_DIR}/memory)
```

---

### 19. `test/memory/test_memory_types.cpp` (test, unit)

**Analog:** `test/reputation/test_reputation.cpp` lines 1-15 (includes + namespace) + `test/common/test_types.cpp` (types tests)

```cpp
/**
 * @file       test_memory_types.cpp
 * @brief      Unit tests for GAML v1 CognitiveAsset types (GAML-01)
 */

#include "common/types.hpp"
#include <gtest/gtest.h>

using namespace sgns::neoswarm;

// ---------------------------------------------------------------------------
// CognitiveAsset default construction (GAML-01)
// ---------------------------------------------------------------------------
TEST(CognitiveAsset, DefaultConstruction)
{
    CognitiveAsset a;
    EXPECT_TRUE(a.m_id.empty());
    EXPECT_TRUE(a.m_entity.empty());
    EXPECT_EQ(a.m_type, MemoryObjectType::fact);
    EXPECT_EQ(a.m_timestamp, 0);
    EXPECT_EQ(a.m_confidence, 0.0f);
    EXPECT_EQ(a.m_provenance, 0.0f);
    EXPECT_EQ(a.m_trustClass, TrustClass::unverified);
}

TEST(CognitiveAsset, DesignatedInitialization)
{
    CognitiveAsset a{
        .m_id = "test-001",
        .m_entity = "physics",
        .m_type = MemoryObjectType::fact,
        .m_timestamp = 1000,
        .m_sourceNode = "node-1",
        .m_confidence = 0.85f,
        .m_provenance = 0.6f,
        .m_trustClass = TrustClass::verified,
    };
    EXPECT_EQ(a.m_id, "test-001");
    EXPECT_EQ(a.m_entity, "physics");
    EXPECT_EQ(a.m_type, MemoryObjectType::fact);
    EXPECT_EQ(a.m_timestamp, 1000);
    EXPECT_EQ(a.m_confidence, 0.85f);
}

TEST(MemoryObjectType, EnumDistinctValues)
{
    // Verify 5 distinct values for 5 subtypes (D-02)
    EXPECT_EQ(static_cast<int>(MemoryObjectType::bridge_block), 0);
    EXPECT_EQ(static_cast<int>(MemoryObjectType::fact), 1);
    EXPECT_EQ(static_cast<int>(MemoryObjectType::policy), 2);
    EXPECT_EQ(static_cast<int>(MemoryObjectType::event), 3);
    EXPECT_EQ(static_cast<int>(MemoryObjectType::tenant_operational), 4);
}

TEST(TrustClass, EnumDistinctValues)
{
    EXPECT_EQ(static_cast<int>(TrustClass::unverified), 0);
    EXPECT_EQ(static_cast<int>(TrustClass::verified), 1);
    EXPECT_NE(static_cast<int>(TrustClass::premium), static_cast<int>(TrustClass::unverified));
}

TEST(MemoryContext, EmptyByDefault)
{
    MemoryContext ctx;
    EXPECT_TRUE(ctx.m_facts.empty());
    EXPECT_TRUE(ctx.m_policies.empty());
}

// ---------------------------------------------------------------------------
// JSON roundtrip (GAML-01)
// ---------------------------------------------------------------------------
#include <nlohmann/json.hpp>

static std::string Serialize(const CognitiveAsset& obj)
{
    nlohmann::json j;
    j["id"] = obj.m_id;
    j["entity"] = obj.m_entity;
    j["type"] = static_cast<int>(obj.m_type);
    j["payload"] = obj.m_payload;
    j["timestamp"] = obj.m_timestamp;
    j["source_node"] = obj.m_sourceNode;
    j["confidence"] = obj.m_confidence;
    j["provenance"] = obj.m_provenance;
    j["trust_class"] = static_cast<int>(obj.m_trustClass);
    return j.dump();
}

static CognitiveAsset Deserialize(const std::string& data)
{
    auto j = nlohmann::json::parse(data);
    CognitiveAsset obj;
    obj.m_id = j.value("id", "");
    obj.m_entity = j.value("entity", "");
    obj.m_type = static_cast<MemoryObjectType>(j.value("type", 0));
    obj.m_payload = j.value("payload", nlohmann::json::object());
    obj.m_timestamp = j.value("timestamp", int64_t(0));
    obj.m_sourceNode = j.value("source_node", "");
    obj.m_confidence = j.value("confidence", 0.0f);
    obj.m_provenance = j.value("provenance", 0.0f);
    obj.m_trustClass = static_cast<TrustClass>(j.value("trust_class", 0));
    return obj;
}

TEST(CognitiveAsset, JsonSerializationRoundtrip)
{
    CognitiveAsset original;
    original.m_id = "roundtrip-1";
    original.m_entity = "chemistry";
    original.m_type = MemoryObjectType::fact;
    original.m_payload = nlohmann::json::object({{"content", "H2O is water"}});
    original.m_timestamp = 1234567890;
    original.m_sourceNode = "node-XYZ";
    original.m_confidence = 0.75f;
    original.m_provenance = 0.5f;
    original.m_trustClass = TrustClass::verified;

    std::string serialized = Serialize(original);
    auto restored = Deserialize(serialized);

    EXPECT_EQ(restored.m_id, "roundtrip-1");
    EXPECT_EQ(restored.m_entity, "chemistry");
    EXPECT_EQ(restored.m_type, MemoryObjectType::fact);
    EXPECT_EQ(restored.m_timestamp, 1234567890);
    EXPECT_EQ(restored.m_sourceNode, "node-XYZ");
    EXPECT_FLOAT_EQ(restored.m_confidence, 0.75f);
    EXPECT_FLOAT_EQ(restored.m_provenance, 0.5f);
    EXPECT_EQ(restored.m_trustClass, TrustClass::verified);
    EXPECT_EQ(restored.m_payload["content"], "H2O is water");
}
```

---

### 20. `test/memory/test_memory_storage.cpp` (test, unit)

**Analog:** `test/reputation/test_reputation.cpp` lines 190-236 (RocksDB test patterns: UniqueDbPath, PutAndGet, GetNotFound, GetAll)

```cpp
/**
 * @file       test_memory_storage.cpp
 * @brief      Unit tests for MemoryStorage RocksDB persistence (GAML-04)
 */

#include "memory/memory_storage.hpp"
#include <chrono>
#include <gtest/gtest.h>

using namespace sgns::neoswarm;
using namespace sgns::neoswarm::memory;

static std::string UniqueDbPath(const std::string& tag)
{
    return "/tmp/genius_test_mem_" + tag + "_" +
           std::to_string(std::chrono::steady_clock::now().time_since_epoch().count());
}

static CognitiveAsset MakeFact(const std::string& id, const std::string& entity,
                                int64_t timestamp, float confidence = 0.5f)
{
    CognitiveAsset a;
    a.m_id = id;
    a.m_entity = entity;
    a.m_type = MemoryObjectType::fact;
    a.m_payload = nlohmann::json::object({{"content", "test fact " + id}});
    a.m_timestamp = timestamp;
    a.m_sourceNode = "test-node";
    a.m_confidence = confidence;
    a.m_provenance = 0.5f;
    a.m_trustClass = TrustClass::unverified;
    return a;
}

// ---------------------------------------------------------------------------
// Open/Close
// ---------------------------------------------------------------------------
TEST(MemoryStorage, OpenAndClose)
{
    MemoryStorage::Config cfg;
    cfg.m_dbPath = UniqueDbPath("openclose");
    MemoryStorage storage(cfg);
    ASSERT_TRUE(storage.Open().has_value());
    EXPECT_TRUE(storage.IsOpen());
    storage.Close();
    EXPECT_FALSE(storage.IsOpen());
}

// ---------------------------------------------------------------------------
// Put / Get roundtrip
// ---------------------------------------------------------------------------
TEST(MemoryStorage, PutAndGet)
{
    MemoryStorage::Config cfg;
    cfg.m_dbPath = UniqueDbPath("putget");
    MemoryStorage storage(cfg);
    ASSERT_TRUE(storage.Open().has_value());

    auto fact = MakeFact("f-1", "physics", 1000, 0.85f);
    ASSERT_TRUE(storage.Put(fact).has_value());

    std::string expectedKey = "physics/1/1000/f-1";
    auto got = storage.Get(expectedKey);
    ASSERT_TRUE(got.has_value());
    EXPECT_EQ(got.value().m_id, "f-1");
    EXPECT_EQ(got.value().m_entity, "physics");
    EXPECT_FLOAT_EQ(got.value().m_confidence, 0.85f);
}

// ---------------------------------------------------------------------------
// Get not found
// ---------------------------------------------------------------------------
TEST(MemoryStorage, GetNotFound)
{
    MemoryStorage::Config cfg;
    cfg.m_dbPath = UniqueDbPath("notfound");
    MemoryStorage storage(cfg);
    ASSERT_TRUE(storage.Open().has_value());
    EXPECT_FALSE(storage.Get("nonexistent/key").has_value());
}

// ---------------------------------------------------------------------------
// GetByPrefix — prefix range scan
// ---------------------------------------------------------------------------
TEST(MemoryStorage, GetByPrefixFiltering)
{
    MemoryStorage::Config cfg;
    cfg.m_dbPath = UniqueDbPath("prefix");
    MemoryStorage storage(cfg);
    ASSERT_TRUE(storage.Open().has_value());

    // Put 3 facts in "physics" and 2 in "chemistry"
    storage.Put(MakeFact("f-1", "physics", 1000, 0.9f));
    storage.Put(MakeFact("f-2", "physics", 2000, 0.7f));
    storage.Put(MakeFact("f-3", "physics", 3000, 0.8f));
    storage.Put(MakeFact("f-4", "chemistry", 1500, 0.6f));
    storage.Put(MakeFact("f-5", "chemistry", 2500, 0.5f));

    // Prefix: physics/fact/
    auto results = storage.GetByPrefix("physics/1/", 10);
    ASSERT_TRUE(results.has_value());
    EXPECT_EQ(results.value().size(), 3u);

    // Prefix: chemistry/fact/ — should get 2
    results = storage.GetByPrefix("chemistry/1/", 10);
    ASSERT_TRUE(results.has_value());
    EXPECT_EQ(results.value().size(), 2u);

    // Prefix that doesn't exist
    results = storage.GetByPrefix("biology/1/", 10);
    ASSERT_TRUE(results.has_value());
    EXPECT_TRUE(results.value().empty());
}

// ---------------------------------------------------------------------------
// PutBatch — atomic multi-put
// ---------------------------------------------------------------------------
TEST(MemoryStorage, PutBatchAtomicity)
{
    MemoryStorage::Config cfg;
    cfg.m_dbPath = UniqueDbPath("batch");
    MemoryStorage storage(cfg);
    ASSERT_TRUE(storage.Open().has_value());

    std::vector<CognitiveAsset> batch;
    batch.push_back(MakeFact("b-1", "math", 1000, 0.8f));
    batch.push_back(MakeFact("b-2", "math", 2000, 0.7f));
    batch.push_back(MakeFact("b-3", "math", 3000, 0.9f));

    ASSERT_TRUE(storage.PutBatch(batch).has_value());

    // Verify all 3 were stored
    auto results = storage.GetByPrefix("math/1/", 10);
    ASSERT_TRUE(results.has_value());
    EXPECT_EQ(results.value().size(), 3u);
}

// ---------------------------------------------------------------------------
// Storage error on unopened DB
// ---------------------------------------------------------------------------
TEST(MemoryStorage, UnopenedStorageReturnsError)
{
    MemoryStorage::Config cfg;
    cfg.m_dbPath = UniqueDbPath("unopened");
    MemoryStorage storage(cfg);
    // Don't call Open()
    EXPECT_FALSE(storage.Put(MakeFact("f", "x", 0)).has_value());
    EXPECT_FALSE(storage.Get("x/1/0/f").has_value());
    EXPECT_FALSE(storage.GetByPrefix("x/1/", 10).has_value());
    EXPECT_FALSE(storage.PutBatch({MakeFact("f", "x", 0)}).has_value());
}
```

---

### 21. `test/memory/test_memory_governor.cpp` (test, unit)

**Analog:** `test/knowledge/test_knowledge_retrieval.cpp` (retrieval test patterns) + `test/reputation/test_reputation.cpp` (storage setup)

```cpp
/**
 * @file       test_memory_governor.cpp
 * @brief      Unit tests for MemoryGovernor heuristic retrieval (GAML-02)
 */

#include "memory/memory_governor.hpp"
#include "memory/memory_storage.hpp"
#include <chrono>
#include <gtest/gtest.h>

using namespace sgns::neoswarm;
using namespace sgns::neoswarm::memory;

static std::string UniqueDbPath(const std::string& tag)
{
    return "/tmp/genius_test_gov_" + tag + "_" +
           std::to_string(std::chrono::steady_clock::now().time_since_epoch().count());
}

static CognitiveAsset MakeFact(const std::string& id, const std::string& entity,
                                const std::string& content, int64_t timestamp,
                                float confidence = 0.5f)
{
    CognitiveAsset a;
    a.m_id = id;
    a.m_entity = entity;
    a.m_type = MemoryObjectType::fact;
    a.m_payload = nlohmann::json::object({{"content", content}});
    a.m_timestamp = timestamp;
    a.m_sourceNode = "node-1";
    a.m_confidence = confidence;
    a.m_provenance = 0.5f;
    a.m_trustClass = TrustClass::unverified;
    return a;
}

class MemoryGovernorTest : public ::testing::Test
{
protected:
    void SetUp() override
    {
        MemoryStorage::Config scfg;
        scfg.m_dbPath = UniqueDbPath("governor");
        m_storage = std::make_unique<MemoryStorage>(scfg);
        ASSERT_TRUE(m_storage->Open().has_value());

        MemoryGovernor::Config gcfg;
        gcfg.m_topK = 5;
        gcfg.m_minConfidence = 0.3f;
        gcfg.m_enabled = true;
        m_governor = std::make_unique<MemoryGovernor>(gcfg, m_storage.get());
    }

    void TearDown() override
    {
        if (m_storage) m_storage->Close();
    }

    std::unique_ptr<MemoryStorage> m_storage;
    std::unique_ptr<MemoryGovernor> m_governor;
};

TEST_F(MemoryGovernorTest, RetrieveReturnsMemoryContext)
{
    // Populate with facts about physics
    int64_t now = std::chrono::steady_clock::now().time_since_epoch().count();
    m_storage->Put(MakeFact("f-1", "physics", "The speed of light is 299792458 m/s", now, 0.9f));
    m_storage->Put(MakeFact("f-2", "physics", "E=mc^2 is the mass-energy equivalence", now - 1000, 0.85f));
    m_storage->Put(MakeFact("f-3", "chemistry", "H2O is water", now, 0.8f));

    Task task;
    task.m_prompt = "What is the speed of light in physics?";
    task.m_nodeId = "test-node";

    ExecutionChain chain;
    chain.m_needsRetrieval = true;

    MemoryContext ctx = m_governor->Retrieve(task, chain);
    EXPECT_GE(ctx.m_facts.size(), 1u);
    // Should not include chemistry fact
    for (const auto& f : ctx.m_facts)
    {
        EXPECT_NE(f.m_entity, "chemistry");
    }
}

TEST_F(MemoryGovernorTest, EmptyDatabaseReturnsEmptyContext)
{
    Task task;
    task.m_prompt = "Explain quantum mechanics";
    task.m_nodeId = "test-node";

    ExecutionChain chain;
    MemoryContext ctx = m_governor->Retrieve(task, chain);
    EXPECT_TRUE(ctx.m_facts.empty());
    EXPECT_TRUE(ctx.m_policies.empty());
}

TEST_F(MemoryGovernorTest, LowConfidenceExcluded)
{
    int64_t now = std::chrono::steady_clock::now().time_since_epoch().count();
    m_storage->Put(MakeFact("f-low", "physics", "Low confidence fact", now, 0.1f));
    m_storage->Put(MakeFact("f-high", "physics", "High confidence fact", now, 0.95f));

    Task task;
    task.m_prompt = "Tell me about physics";
    task.m_nodeId = "test-node";

    ExecutionChain chain;
    MemoryContext ctx = m_governor->Retrieve(task, chain);

    // Should only have the high-confidence fact
    ASSERT_EQ(ctx.m_facts.size(), 1u);
    EXPECT_EQ(ctx.m_facts[0].m_id, "f-high");
}

TEST_F(MemoryGovernorTest, DisabledGovernorReturnsEmpty)
{
    MemoryGovernor::Config disabledCfg;
    disabledCfg.m_enabled = false;
    MemoryGovernor disabledGov(disabledCfg, m_storage.get());

    Task task;
    task.m_prompt = "test";
    ExecutionChain chain;
    MemoryContext ctx = disabledGov.Retrieve(task, chain);
    EXPECT_TRUE(ctx.m_facts.empty());
}

TEST_F(MemoryGovernorTest, ConfidenceRankedResults)
{
    int64_t now = std::chrono::steady_clock::now().time_since_epoch().count();
    m_storage->Put(MakeFact("f-mid", "physics", "Mid", now, 0.5f));
    m_storage->Put(MakeFact("f-high", "physics", "High", now, 0.9f));
    m_storage->Put(MakeFact("f-low", "physics", "Low", now, 0.4f));

    Task task;
    task.m_prompt = "physics facts";
    task.m_nodeId = "test-node";

    ExecutionChain chain;
    MemoryContext ctx = m_governor->Retrieve(task, chain);

    ASSERT_EQ(ctx.m_facts.size(), 3u);
    // Results should be in confidence-descending order
    EXPECT_GE(ctx.m_facts[0].m_confidence, ctx.m_facts[1].m_confidence);
    EXPECT_GE(ctx.m_facts[1].m_confidence, ctx.m_facts[2].m_confidence);
}
```

---

### 22. `test/memory/test_memory_ingestion.cpp` (test, unit)

**Analog:** `test/elm/test_elm.cpp` (MockEngine pattern) + `test/reputation/test_reputation.cpp` (storage patterns)

```cpp
/**
 * @file       test_memory_ingestion.cpp
 * @brief      Unit tests for the 3-stage ingestion pipeline (GAML-03)
 */

#include "memory/fact_extraction.hpp"
#include "memory/context_mapping.hpp"
#include "memory/write_evaluation.hpp"
#include "memory/memory_storage.hpp"
#include <chrono>
#include <gtest/gtest.h>

using namespace sgns::neoswarm;
using namespace sgns::neoswarm::memory;

static std::string UniqueDbPath(const std::string& tag)
{
    return "/tmp/genius_test_ingest_" + tag + "_" +
           std::to_string(std::chrono::steady_clock::now().time_since_epoch().count());
}

// ---------------------------------------------------------------------------
// FactExtraction (GAML-03)
// ---------------------------------------------------------------------------
TEST(FactExtraction, ExtractsDeclarativeFacts)
{
    FactExtraction extractor;
    Task task;
    task.m_id = "task-1";
    task.m_nodeId = "node-1";

    std::string text = "The speed of light is approximately 299,792,458 meters per second. "
                       "This was measured by Michelson. "
                       "Is light really that fast?";

    auto facts = extractor.Extract(text, task);
    ASSERT_TRUE(facts.has_value());
    // At least one declarative fact should be extracted (question excluded)
    EXPECT_GE(facts.value().size(), 1u);

    for (const auto& f : facts.value())
    {
        EXPECT_EQ(f.m_type, MemoryObjectType::fact);
        EXPECT_FALSE(f.m_id.empty());
    }
}

TEST(FactExtraction, RespectsMaxFactsLimit)
{
    FactExtraction::Config cfg;
    cfg.m_maxFacts = 2;
    FactExtraction extractor(cfg);

    Task task;
    task.m_id = "task-1";
    task.m_nodeId = "node-1";

    std::string text;
    for (int i = 0; i < 10; ++i)
    {
        text += "The value is " + std::to_string(i) + ". ";
    }

    auto facts = extractor.Extract(text, task);
    ASSERT_TRUE(facts.has_value());
    EXPECT_LE(facts.value().size(), 2u);
}

TEST(FactExtraction, EmptyTextReturnsEmpty)
{
    FactExtraction extractor;
    Task task;
    auto facts = extractor.Extract("", task);
    ASSERT_TRUE(facts.has_value());
    EXPECT_TRUE(facts.value().empty());
}

// ---------------------------------------------------------------------------
// ContextMapping (GAML-03)
// ---------------------------------------------------------------------------
TEST(ContextMapping, AssignsEntityAndTrustClass)
{
    ContextMapping mapper;
    Task task;
    task.m_prompt = "Tell me about quantum mechanics and wave functions";

    std::vector<CognitiveAsset> facts;
    CognitiveAsset f;
    f.m_id = "f-1";
    facts.push_back(f);

    auto mapped = mapper.Map(facts, task);
    ASSERT_EQ(mapped.size(), 1u);
    EXPECT_FALSE(mapped[0].m_entity.empty());
    EXPECT_EQ(mapped[0].m_trustClass, TrustClass::unverified);
    EXPECT_GT(mapped[0].m_provenance, 0.0f);
}

// ---------------------------------------------------------------------------
// WriteEvaluation (GAML-03)
// ---------------------------------------------------------------------------
TEST(WriteEvaluation, ScoresAndFilters)
{
    MemoryStorage::Config scfg;
    scfg.m_dbPath = UniqueDbPath("writeeval");
    MemoryStorage storage(scfg);
    ASSERT_TRUE(storage.Open().has_value());

    WriteEvaluation::Config cfg;
    cfg.m_noveltyThreshold = 0.1f;
    cfg.m_utilityThreshold = 0.1f;
    cfg.m_overallThreshold = 0.2f;
    WriteEvaluation evaluator(cfg);

    CognitiveAsset fact;
    fact.m_id = "unique-fact";
    fact.m_entity = "physics";
    fact.m_type = MemoryObjectType::fact;
    fact.m_payload = nlohmann::json::object({{"content", "The Higgs boson was discovered at CERN in 2012."}});
    fact.m_confidence = 0.5f;

    std::vector<CognitiveAsset> facts = { fact };
    auto accepted = evaluator.Evaluate(std::move(facts), &storage);
    ASSERT_TRUE(accepted.has_value());
    EXPECT_EQ(accepted.value().size(), 1u);

    storage.Close();
}

TEST(WriteEvaluation, DisabledPassesAll)
{
    WriteEvaluation::Config cfg;
    cfg.m_enabled = false;
    WriteEvaluation evaluator(cfg);

    CognitiveAsset fact;
    fact.m_id = "f-1";
    fact.m_payload = nlohmann::json::object({{"content", "test"}});

    auto accepted = evaluator.Evaluate({ fact }, nullptr);
    ASSERT_TRUE(accepted.has_value());
    EXPECT_EQ(accepted.value().size(), 1u);
}

// ---------------------------------------------------------------------------
// Pipeline end-to-end (GAML-03)
// ---------------------------------------------------------------------------
TEST(IngestionPipeline, EndToEnd)
{
    MemoryStorage::Config scfg;
    scfg.m_dbPath = UniqueDbPath("e2e");
    MemoryStorage storage(scfg);
    ASSERT_TRUE(storage.Open().has_value());

    Task task;
    task.m_id = "test-task";
    task.m_nodeId = "node-1";
    task.m_prompt = "Explain the speed of light in physics";

    std::string output = "The speed of light in vacuum is exactly 299,792,458 meters per second. "
                         "This is a fundamental constant in physics. "
                         "It was first accurately measured by Albert Michelson.";

    // Stage 1
    FactExtraction extractor;
    auto extracted = extractor.Extract(output, task);
    ASSERT_TRUE(extracted.has_value());
    ASSERT_GE(extracted.value().size(), 1u);

    // Stage 2
    ContextMapping mapper;
    auto mapped = mapper.Map(std::move(extracted.value()), task);
    ASSERT_GE(mapped.size(), 1u);

    // Stage 3
    WriteEvaluation evaluator;
    auto accepted = evaluator.Evaluate(std::move(mapped), &storage);
    ASSERT_TRUE(accepted.has_value());
    EXPECT_GE(accepted.value().size(), 1u);

    // Persist accepted facts
    auto putRes = storage.PutBatch(accepted.value());
    EXPECT_TRUE(putRes.has_value());

    // Verify they can be retrieved
    auto retrieved = storage.GetByPrefix("explain_the_speed/1/", 10);
    ASSERT_TRUE(retrieved.has_value());
    EXPECT_GE(retrieved.value().size(), 1u);

    storage.Close();
}
```

---

### 23. `test/CMakeLists.txt` (modify — config)

**Analog:** Self (lines 55-81), add memory test entries following the `neoswarm_test` macro pattern.

**Add after the ELM test entry** (after line 81):
```cmake
# Phase 8 — Agentic Memory (GAML v1)
neoswarm_test(test_memory_types         memory/test_memory_types.cpp         "neoswarm_memory;neoswarm_common")
neoswarm_test(test_memory_storage       memory/test_memory_storage.cpp       "neoswarm_memory;neoswarm_common")
neoswarm_test(test_memory_governor      memory/test_memory_governor.cpp      "neoswarm_memory;neoswarm_common")
neoswarm_test(test_memory_ingestion     memory/test_memory_ingestion.cpp     "neoswarm_memory;neoswarm_common")
```

**Also add to `src/api/CMakeLists.txt`** — ensure `neoswarm_api` links `neoswarm_memory`:
```cmake
target_link_libraries(neoswarm_api PUBLIC neoswarm_memory)
```
*(This is needed because ApiServer includes memory headers. Check the actual `src/api/CMakeLists.txt` to confirm the link list.)*

---

## Shared Patterns

### Authentication / Authorization
**Source:** Not applicable for Phase 8 — local-only memory store, no auth boundary. Future phases (privacy classification, Phase 10) will add auth.

### Error Handling
**Source:** `src/common/error.hpp` lines 18-44 + `src/api/api_server.cpp` lines 104-106, 211-216
**Apply to:** All memory files (service, utility, controller)

```cpp
// Pattern: outcome::result<T> with explicit check (D-19)
auto result = m_storage->Open();
if (!result.has_value())
{
    ServerLogger()->warn("Memory storage open failed — memory disabled");
    // D-20: NOT fatal
}

// Pattern: "not found" is expected, not an error (D-20)
if (status.IsNotFound())  // From reputation_storage.cpp:147
    return outcome::failure(Error::MemoryNotFound);

// Pattern: empty retrieval = empty context, not error (D-20)
auto ctx = m_governor->Retrieve(task, chain);
// ctx.m_facts may be empty — that's OK, continue without memory
```

### Logging
**Source:** `src/common/logging.hpp` lines 25-36 + `src/reputation/reputation_storage.cpp` lines 19-25
**Apply to:** All memory .cpp files

```cpp
// Pattern: anonymous namespace logger per module
namespace {
    auto StorageLogger() {
        return neoswarm::CreateLogger("MemoryStorage");
    }
}

// Usage (from reputation_storage.cpp:96):
StorageLogger()->info("MemoryStorage opened: {}", m_cfg.m_dbPath);
StorageLogger()->warn("Memory storage open failed — memory disabled");
StorageLogger()->error("JSON deserialization failed: {}", e.what());
StorageLogger()->debug("Memory ingested {} facts", accepted.size());
```

### Configuration Struct Pattern
**Source:** `src/knowledge/knowledge_retrieval.hpp` lines 27-34 + `src/knowledge/context_injection.hpp` lines 22-26
**Apply to:** All memory classes (MemoryStorage, MemoryGovernor, FactExtraction, ContextMapping, WriteEvaluation)

```cpp
// Pattern: nested Config struct with sensible defaults
struct Config
{
    std::string m_dbPath = "./memory.db";
    int m_topK = 10;
    float m_minConfidence = 0.3f;
    int64_t m_maxAgeNs = 86400LL * 1000000000LL; // 24h
    bool m_enabled = true;
};

// Constructor takes Config by value (move)
explicit MemoryGovernor(Config cfg, MemoryStorage* storage);
```

### Pimpl (Pointer to Implementation)
**Source:** `src/reputation/reputation_storage.hpp` lines 82-84
**Apply to:** MemoryStorage only (Phase 8)

```cpp
// Pattern: header has ZERO RocksDB includes
struct Impl;
std::unique_ptr<Impl> m_impl;

// .cpp defines the real struct
struct MemoryStorage::Impl
{
    rocksdb::DB* m_db = nullptr;
    rocksdb::Options m_options;
};
```

### RocksDB Iterator Cleanup
**Source:** `src/reputation/reputation_storage.cpp` lines 187-198
**Apply to:** MemoryStorage::GetByPrefix

```cpp
// Pattern: raw new → delete (RocksDB predates smart pointers)
auto* it = m_impl->m_db->NewIterator(rocksdb::ReadOptions());
for (it->Seek(prefix); it->Valid(); it->Next())
{
    // ...
}
delete it;  // MUST be called — NOT a memory leak
// Anti-pattern: wrapping in unique_ptr is cleaner but project convention is raw
```

### Outcome Error Checking Pattern
**Source:** `src/api/api_server.cpp` lines 103-106, 211-213, 291-294
**Apply to:** All functions returning outcome::result<T>

```cpp
// Pattern: BOOST_OUTCOME_TRY for propagation (from api_server.cpp:70)
BOOST_OUTCOME_TRY(m_identity->Generate());

// Pattern: explicit has_value() check for graceful degradation
if (!res.has_value())
{
    ServerLogger()->warn("Operation failed — continuing");
    return outcome::failure(res.error());
}

// Pattern: no (void) discards (D-19)
(void)m_storage->Open();  // explicit (void) cast when intentionally discarding
```

### Thread Safety (Mutex)
**Source:** `src/reputation/reputation_crdt.hpp` lines 28-32
**Apply to:** MemoryGovernor (future concurrent access), MemoryStorage::Put/PutBatch

```cpp
// Pattern: mutable mutex for const methods
mutable std::mutex m_mutex;

void Put(const CognitiveAsset& obj)
{
    std::lock_guard<std::mutex> lock(m_mutex);
    // ... RocksDB write ...
}
```

### Namespace Organization
**Source:** `src/reputation/reputation_storage.hpp` line 17
**Apply to:** All memory files

```cpp
// Pattern: nested namespace with module-level scope
namespace sgns::neoswarm::memory
{
    class MemoryStorage { /* ... */ };
} // namespace sgns::neoswarm::memory
```

### CMake Library Pattern
**Source:** `src/reputation/CMakeLists.txt` lines 1-22
**Apply to:** `src/memory/CMakeLists.txt`

```cmake
# Pattern: STATIC library, conditional linking for RocksDB
add_library(neoswarm_memory STATIC ...)
target_include_directories(neoswarm_memory PUBLIC ...)
target_link_libraries(neoswarm_memory PUBLIC neoswarm_common)
if(TARGET RocksDB::rocksdb)
    target_link_libraries(neoswarm_memory PUBLIC RocksDB::rocksdb)
endif()
```

### Test Patterns
**Source:** `test/reputation/test_reputation.cpp` lines 190-236 + `test/CMakeLists.txt` lines 55-81
**Apply to:** All memory test files

```cpp
// Pattern: UniqueDbPath for isolated tests (lines 190-194)
static std::string UniqueDbPath(const std::string& tag)
{
    return "/tmp/genius_test_" + tag + "_" +
           std::to_string(std::chrono::steady_clock::now().time_since_epoch().count());
}

// Pattern: neoswarm_test macro (line 55)
neoswarm_test(test_memory_storage memory/test_memory_storage.cpp "neoswarm_memory;neoswarm_common")

// Pattern: ASSERT_TRUE for Open, ASSERT_TRUE for Put, ASSERT_TRUE for Get
// Pattern: NO std::this_thread::sleep_for in tests (per CLAUDE.md)
```

---

## No Analog Found

All Phase 8 files have close analogs in the existing codebase. The patterns are well-established:
- RocksDB Persistence: exact match with `ReputationStorage`
- Retrieval Orchestrator: role-match with `KnowledgeRetrieval`
- Regex Parsing: role-match with `PromptAnalyzer`
- Context Injection: role-match with `ContextInjection`
- Test Patterns: exact match with reputation tests

**No files without close analog.**

## Metadata

**Analog search scope:** `src/` (all production code), `test/` (all test code)
**Files scanned:** 18 analog files
**Pattern extraction date:** 2026-07-23
**Key patterns identified:**
1. RocksDB Pimpl (ReputationStorage) — exact template for MemoryStorage
2. Config struct + Pimpl (KnowledgeRetrieval) — exact template for MemoryGovernor
3. std::regex + keyword matching (PromptAnalyzer) — exact template for FactExtraction
4. Single-method injection class (ContextInjection) — exact template for ContextMapping + WriteEvaluation
5. outcome::result + graceful degradation (ApiServer) — exact template for all error handling
6. neoswarm_test macro + UniqueDbPath (test suite) — exact template for all memory tests
