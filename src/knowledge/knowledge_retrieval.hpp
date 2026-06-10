/**
 * @file       m_knowledgeretrieval.hpp
 * @brief      Query embedding and ANN search for Grokipedia facts (PTDS §8.2)
 * @date       2026-05-06
 * @author     Subaskar S (ssivakumar@gnus.ai)
 */

#ifndef NEOSWARM_KNOWLEDGE_KNOWLEDGERETRIEVAL_HPP
#define NEOSWARM_KNOWLEDGE_KNOWLEDGERETRIEVAL_HPP

#include "common/error.hpp"
#include "common/types.hpp"
#include <memory>
#include <string>
#include <vector>

namespace sgns::neoswarm::knowledge
{
    /**
     * @brief Retrieves top-k structured facts from a Grokipedia index.
     *
     * Uses a simple TF-IDF bag-of-words embedding with cosine similarity.
     * Degrades gracefully when the index is unavailable.
     */
    class KnowledgeRetrieval
    {
        public:
        struct Config
        {
            std::string index_path_ = ""; ///< path to HNSW index file (future)
            std::string m_factsPath = ""; ///< path to facts CSV
            int top_k_ = 3;               ///< number of facts to retrieve
            float min_score_ = 0.5f;      ///< minimum relevance score
            bool enabled_ = true;
        };

        KnowledgeRetrieval();
        explicit KnowledgeRetrieval( Config cfg );
        ~KnowledgeRetrieval();

        /**
         * @brief Load the knowledge index from disk.
         * @return outcome::success or KnowledgeUnavailable.
         */
        outcome::result<void> Load();

        /// @return True if the index has been loaded.
        bool IsLoaded() const
        {
            return m_loaded;
        }

        /**
         * @brief Retrieve top-k facts relevant to the query.
         * @param query  User prompt or search string.
         * @return       Vector of KnowledgeFact or KnowledgeUnavailable.
         */
        outcome::result<std::vector<KnowledgeFact>> Retrieve( const std::string& query ) const;

        private:
        struct Impl;
        std::unique_ptr<Impl> m_impl;
        Config m_cfg;
        bool m_loaded = false;

        /**
         * @brief Compute a simple bag-of-words TF-IDF embedding.
         * @param text  Input string.
         * @return      L2-normalised embedding vector.
         */
        std::vector<float> Embed( const std::string& text ) const;

        /**
         * @brief Compute cosine similarity between two L2-normalised vectors.
         * @param a  First vector.
         * @param b  Second vector.
         * @return   Similarity in [0, 1].
         */
        static float CosineSimilarity( const std::vector<float>& a, const std::vector<float>& b );
    };

} // namespace sgns::neoswarm::knowledge

#endif // NEOSWARM_KNOWLEDGE_KNOWLEDGERETRIEVAL_HPP
