/**
 * @file       context_injection.hpp
 * @brief      Augments prompts with Grokipedia facts (PTDS §8.2)
 * @date       2026-05-06
 */

#ifndef NEOSWARM_KNOWLEDGE_CONTEXTINJECTION_HPP
#define NEOSWARM_KNOWLEDGE_CONTEXTINJECTION_HPP

#include "common/types.hpp"
#include <string>
#include <vector>

namespace sgns::neoswarm::knowledge
{
    /**
     * @brief Prepends retrieved Grokipedia facts to a prompt before inference.
     */
    class ContextInjection
    {
        public:
        struct Config
        {
            size_t max_token_budget_ = 256; ///< max tokens to add for context
            bool add_source_tags_ = true;   ///< add [GROKIPEDIA: source] tags
        };

        ContextInjection();
        explicit ContextInjection( Config cfg );

        /**
         * @brief Inject facts into a prompt before inference.
         * @param prompt  Original user prompt.
         * @param facts   Retrieved knowledge facts.
         * @return        Augmented prompt string.
         */
        std::string Inject( const std::string& prompt, const std::vector<KnowledgeFact>& facts ) const;

        private:
        Config m_cfg;

        /**
         * @brief Estimate token count (rough: chars / 4).
         * @param text  Input string.
         * @return      Estimated token count.
         */
        static size_t EstimateTokens( const std::string& text );
    };

} // namespace sgns::neoswarm::knowledge

#endif // NEOSWARM_KNOWLEDGE_CONTEXTINJECTION_HPP
