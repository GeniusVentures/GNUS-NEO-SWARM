/**
 * @file       sg_processing_bridge.hpp
 * @brief      Bridge to SuperGenius SGProcessingManager for GNUS network dispatch
 * @date       2026-05-06
 * @author     Subaskar S (ssivakumar@gnus.ai)
 */

#ifndef NEOSWARM_CORE_SGPROCESSING_SGPROCESSINGBRIDGE_HPP
#define NEOSWARM_CORE_SGPROCESSING_SGPROCESSINGBRIDGE_HPP

#include "common/error.hpp"
#include <cstdint>
#include <memory>
#include <string>
#include <vector>

namespace boost::asio
{
    class io_context;
} // namespace boost::asio

namespace sgns
{
    enum class InputFormat : int;
} // namespace sgns

namespace sgns::neoswarm::network
{
    class SuperGeniusClient;
}

namespace sgns::neoswarm::core
{
    /**
     * @brief Constructs GNUS_Schema-compliant JSON and submits inference jobs
     *        to SGProcessingManager (Phase 1 direct) or the GNUS network (Phase 2).
     */
    class SGProcessingBridge
    {
        public:
        struct Config
        {
            bool network_mode_ = false; ///< Phase 2: dispatch via gRPCForSuperGenius
        };

        SGProcessingBridge();
        explicit SGProcessingBridge( Config cfg );
        ~SGProcessingBridge() = default;

        /**
         * @brief Set the SuperGeniusClient for Phase 2 network dispatch.
         * @param client  The SuperGeniusClient instance (owned by ApiServer).
         */
        void SetClient( network::SuperGeniusClient* client ) noexcept;

        /**
         * @brief Build a GNUS_Schema JSON string from the supplied parameters.
         * @param model_uri    IPFS URI or path to the MNN model.
         * @param input_uri    IPFS URI or path to the input data.
         * @param input_format Tensor element format.
         * @param shape        Tensor shape dimensions.
         * @return             JSON string or InvalidArgument.
         */
        outcome::result<std::string> BuildSchemaJson( const std::string& model_uri,
                                                      const std::string& input_uri,
                                                      sgns::InputFormat input_format,
                                                      const std::vector<int64_t>& shape ) const;

        /**
         * @brief Submit a job and return raw tensor output bytes.
         *
         * Phase 1 (network_mode_=false): calls ProcessingManager::Create + Process.
         * Phase 2 (network_mode_=true):  dispatches via gRPCForSuperGenius (stub).
         *
         * @param model_uri    IPFS URI or path to the MNN model.
         * @param input_uri    IPFS URI or path to the input data.
         * @param input_format Tensor element format.
         * @param shape        Tensor shape dimensions.
         * @param ioc          Boost ASIO io_context for async operations.
         * @return             Raw output bytes or InferenceFailed / NotImplemented.
         */
        outcome::result<std::vector<uint8_t>> SubmitJob( const std::string& model_uri,
                                                         const std::string& input_uri,
                                                         sgns::InputFormat input_format,
                                                         const std::vector<int64_t>& shape,
                                                         std::shared_ptr<boost::asio::io_context> ioc );

        private:
        Config cfg_;
        network::SuperGeniusClient* client_ = nullptr;

        outcome::result<std::vector<uint8_t>> SubmitDirect( const std::string& jsondata,
                                                            std::shared_ptr<boost::asio::io_context> ioc ) const;

        outcome::result<std::vector<uint8_t>> SubmitNetwork( const std::string& jsondata ) const;
    };

} // namespace sgns::neoswarm::core

#endif // NEOSWARM_CORE_SGPROCESSING_SGPROCESSINGBRIDGE_HPP
