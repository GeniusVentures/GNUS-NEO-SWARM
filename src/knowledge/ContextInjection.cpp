/**
 * @file       ContextInjection.cpp
 * @brief      Prompt augmentation with Grokipedia facts
 * @date       2026-05-06
 * @author     Subaskar S (ssivakumar@gnus.ai)
 */

#include "ContextInjection.hpp"

namespace sgns::neoswarm::knowledge
{
    ContextInjection::ContextInjection() : cfg_( {} ) {}
    ContextInjection::ContextInjection( Config cfg ) : cfg_( std::move( cfg ) ) {}

    size_t ContextInjection::EstimateTokens( const std::string &text )
    {
        return text.size() / 4;
    }

    std::string ContextInjection::Inject( const std::string              &prompt,
                                          const std::vector<KnowledgeFact> &facts ) const
    {
        if ( facts.empty() )
        {
            return prompt;
        }

        std::string context;
        size_t      used_tokens = 0;

        for ( const auto &fact : facts )
        {
            std::string entry;
            if ( cfg_.add_source_tags_ )
            {
                entry = "[GROKIPEDIA: " + fact.source_ + "] " + fact.content_ + "\n";
            }
            else
            {
                entry = fact.content_ + "\n";
            }

            size_t entry_tokens = EstimateTokens( entry );
            if ( used_tokens + entry_tokens > cfg_.max_token_budget_ )
            {
                break;
            }

            context     += entry;
            used_tokens += entry_tokens;
        }

        if ( context.empty() )
        {
            return prompt;
        }

        return "Context from Grokipedia:\n" + context + "\n" + prompt;
    }

} // namespace sgns::neoswarm::knowledge
