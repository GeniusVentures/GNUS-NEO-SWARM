/**
 * @file       grammar_specialist.hpp
 * @brief      Grammar correction specialist model (PTDS §5.2)
 * @date       2026-05-06
 * @author     Subaskar S (ssivakumar@gnus.ai)
 */

#ifndef NEOSWARM_SPECIALISTS_GRAMMARSPECIALIST_HPP_
#define NEOSWARM_SPECIALISTS_GRAMMARSPECIALIST_HPP_

#include "i_specialist.hpp"
#include "core/engine/inference_engine.hpp"
#include <memory>

namespace sgns::neoswarm::specialists
{
    /**
     * @brief 200M–500M parameter grammar correction model (PTDS §5.2).
     *
     * Post-processes Core LLM output for style, consistency, and linguistic
     * correctness. Runs as a sequential stage after Core inference.
     */
    class GrammarSpecialist : public ISpecialist
    {
        public:
        explicit GrammarSpecialist( std::shared_ptr<core::InferenceEngine> engine = nullptr );

        std::string GetName() const override
        {
            return "GrammarSpecialist";
        }
        bool IsLoaded() const override
        {
            return loaded_;
        }

        outcome::result<void> Load( const std::string& model_path ) override;
        outcome::result<std::string> Process( const std::string& input ) override;
        float GetConfidence() const override
        {
            return last_confidence_;
        }

        private:
        std::shared_ptr<core::InferenceEngine> engine_;
        bool loaded_ = false;
        float last_confidence_ = 0.0f;

        std::string BuildPrompt( const std::string& input ) const;
    };

} // namespace sgns::neoswarm::specialists

#endif // NEOSWARM_SPECIALISTS_GRAMMARSPECIALIST_HPP_
