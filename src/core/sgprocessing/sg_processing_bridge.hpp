/**
 * @file       sg_processing_bridge.hpp
 * @brief      Bridge to SuperGenius SGProcessingManager for GNUS network dispatch
 * @date       2026-05-06
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
    class SGClient;
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
            bool m_networkMode = false; ///< Phase 2: dispatch via gRPCForSuperGenius
        };

        SGProcessingBridge();
        explicit SGProcessingBridge( Config cfg );
        ~SGProcessingBridge() = default;

        /**
         * @brief Set the SGClient for Phase 2 network dispatch.
         * @param client  The SGClient instance (owned by ApiServer).
         */
        void SetClient( network::SGClient* client ) noexcept;

        /**
         * @brief Build a GNUS_Schema JSON string from the supplied parameters.
         * @param model_uri    IPFS URI or path to the MNN model.
         * @param input_uri    IPFS URI or path to the input data.
         * @param input_format Tensor element format.
         * @param shape        Tensor shape dimensions (one block/window's shape).
         * @param total_width  Total input element count, for inputs processed as multiple
         *                     windows over data wider than one block. 0 => derive from
         *                     `shape` (product of its dims), i.e. the whole input is one block.
         * @param chunk_stride Step between window starts. 0 => defaults to `shape.back()`
         *                     (the block length), i.e. non-overlapping windows.
         * @return             JSON string or InvalidArgument.
         */
        outcome::result<std::string> BuildSchemaJson( const std::string& model_uri,
                                                      const std::string& input_uri,
                                                      sgns::InputFormat input_format,
                                                      const std::vector<int64_t>& shape,
                                                      int64_t total_width = 0,
                                                      int64_t chunk_stride = 0 ) const;

        /**
         * @brief Submit a job and return raw tensor output bytes.
         *
         * Phase 1 (m_networkMode=false): calls ProcessingManager::Create + Process.
         * Phase 2 (m_networkMode=true):  dispatches via gRPCForSuperGenius (stub).
         *
         * @param model_uri    IPFS URI or path to the MNN model.
         * @param input_uri    IPFS URI or path to the input data.
         * @param input_format Tensor element format.
         * @param shape        Tensor shape dimensions (one block/window's shape).
         * @param ioc          Boost ASIO io_context for async operations.
         * @param total_width  Total input element count; see BuildSchemaJson().
         * @param chunk_stride Step between window starts; see BuildSchemaJson().
         * @return             Raw output bytes or InferenceFailed / NotImplemented.
         */
        outcome::result<std::vector<uint8_t>> SubmitJob( const std::string& model_uri,
                                                         const std::string& input_uri,
                                                         sgns::InputFormat input_format,
                                                         const std::vector<int64_t>& shape,
                                                         std::shared_ptr<boost::asio::io_context> ioc,
                                                         int64_t total_width = 0,
                                                         int64_t chunk_stride = 0 );

            /**
         * @brief Run a pre-built GNUS_Schema JSON through the local direct-call
         *        path (Phase 13, SGF-01: exposed for tests/integrations that
         *        need to inject schema `parameters` — e.g. the MNN session
         *        `backend` selector — which SubmitJob's schema builder does
         *        not emit).
         *
         * Calls ProcessingManager::Create() + Process() directly — the exact
         * same body SubmitJob() reaches when m_networkMode is false.
         *
         * @param jsondata GNUS_Schema JSON (e.g. from BuildSchemaJson, patched).
         * @param ioc      Boost ASIO io_context for async operations.
         * @return         Raw output bytes or InferenceFailed.
         */
        outcome::result<std::vector<uint8_t>> SubmitDirect( const std::string& jsondata,
                                                            std::shared_ptr<boost::asio::io_context> ioc ) const;

    private:
        Config m_cfg;
        network::SGClient* m_client = nullptr;

        outcome::result<std::vector<uint8_t>> SubmitNetwork( const std::string& jsondata ) const;
    };

} // namespace sgns::neoswarm::core

#endif // NEOSWARM_CORE_SGPROCESSING_SGPROCESSINGBRIDGE_HPP
