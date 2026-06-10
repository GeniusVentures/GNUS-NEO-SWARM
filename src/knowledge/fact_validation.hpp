/**
 * @file       fact_validation.hpp
 * @brief      Post-generation fact checking against Grokipedia (PTDS §8.3)
 * @date       2026-05-06
 * @author     Subaskar S (ssivakumar@gnus.ai)
 */

#ifndef NEOSWARM_KNOWLEDGE_FACTVALIDATION_HPP
#define NEOSWARM_KNOWLEDGE_FACTVALIDATION_HPP

#include "m_knowledgeretrieval.hpp"
#include "common/types.hpp"
#include <memory>
#include <string>
#include <vector>

namespace sgns::neoswarm::knowledge
{
    /**
     * @brief Checks factual claims in generated output against Grokipedia.
     *
     * A contradiction lowers the node's consistency_score and may trigger
     * regeneration.
     */
    class FactValidation
    {
        public:
        struct ValidationResult
        {
            bool passed_ = true;
            float contradiction_score_ = 0.0f; ///< 0=none, 1=full
            std::vector<std::string> contradictions_;
            std::string suggestion_;
        };

        /**
         * @brief Construct with a shared knowledge retrieval instance.
         * @param retrieval  Loaded KnowledgeRetrieval to check against.
         */
        explicit FactValidation( std::shared_ptr<KnowledgeRetrieval> retrieval );

        /**
         * @brief Validate generated output against retrieved grounding facts.
         * @param output          Generated text to validate.
         * @param grounding_facts Facts that were injected into the prompt.
         * @return                ValidationResult with contradiction details.
         */
        ValidationResult Validate( const std::string& output, const std::vector<KnowledgeFact>& grounding_facts ) const;

        /// @return True if the retrieval index is loaded and validation is possible.
        bool IsAvailable() const;

        private:
        std::shared_ptr<KnowledgeRetrieval> retrieval_;

        /**
         * @brief Extract numeric claims from text.
         * @param text  Input string.
         * @return      Vector of (claim_text, numeric_value) pairs.
         */
        std::vector<std::pair<std::string, double>> ExtractNumericClaims( const std::string& text ) const;

        /**
         * @brief Check if a numeric claim contradicts a known fact string.
         * @param claim        Claimed numeric value.
         * @param fact_content Fact content string to check against.
         * @return             True if a contradiction is detected.
         */
        bool Contradicts( double claim, const std::string& fact_content ) const;
    };

} // namespace sgns::neoswarm::knowledge

#endif // NEOSWARM_KNOWLEDGE_FACTVALIDATION_HPP
