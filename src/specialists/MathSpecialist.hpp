/**
 * @file       MathSpecialist.hpp
 * @brief      GSM8K-tuned math specialist model (PTDS §5.2)
 * @date       2026-05-06
 * @author     Subaskar S (ssivakumar@gnus.ai)
 */

#ifndef NEOSWARM_SPECIALISTS_MATHSPECIALIST_HPP_
#define NEOSWARM_SPECIALISTS_MATHSPECIALIST_HPP_

#include "ISpecialist.hpp"
#include "SymbolicFallback.hpp"
#include "core/engine/InferenceEngine.hpp"
#include <memory>
#include <optional>

namespace sgns::neoswarm::specialists
{
    /**
     * @brief 1–3B parameter GSM8K-tuned math model (PTDS §5.2).
     *
     * Activated by the router when numeric density > threshold.
     * Includes symbolic fallback when model confidence < kConfidenceThreshold.
     */
    class MathSpecialist : public ISpecialist
    {
    public:
        explicit MathSpecialist(
            std::shared_ptr<core::InferenceEngine> engine = nullptr );

        std::string GetName()  const override { return "MathSpecialist"; }
        bool        IsLoaded() const override { return loaded_; }

        outcome::result<void>        Load( const std::string &model_path ) override;
        outcome::result<std::string> Process( const std::string &input ) override;
        float                        GetConfidence() const override { return last_confidence_; }

    private:
        std::shared_ptr<core::InferenceEngine> engine_;
        bool                                   loaded_          = false;
        float                                  last_confidence_ = 0.0f;

        std::string              BuildPrompt( const std::string &input ) const;
        std::optional<std::string> TrySymbolicFallback( const std::string &input ) const;
    };

} // namespace sgns::neoswarm::specialists

#endif // NEOSWARM_SPECIALISTS_MATHSPECIALIST_HPP_
