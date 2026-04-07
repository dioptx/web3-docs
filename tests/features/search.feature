Feature: Proposal Search
  As a web3 developer using an AI assistant
  I want to search across all protocol proposals by keyword or concept
  So that I can discover relevant EIPs, BIPs, ERCs, and SIMDs

  Background:
    Given a database with the following proposals
      | id        | chain    | type | number | title                                | status | category | authors               | description                        |
      | eip-1559  | ethereum | eip  | 1559   | Fee market change for ETH 1.0 chain  | Final  | Core     | Vitalik Buterin       | Base fee burning mechanism         |
      | eip-4844  | ethereum | eip  | 4844   | Shard Blob Transactions              | Final  | Core     | Vitalik Buterin       | Proto-danksharding blob txs        |
      | erc-20    | ethereum | erc  | 20     | Token Standard                       | Final  | ERC      | Fabian Vogelsteller   | Standard interface for tokens      |
      | erc-721   | ethereum | erc  | 721    | Non-Fungible Token Standard          | Final  | ERC      | William Entriken      | NFT standard interface             |
      | bip-141   | bitcoin  | bip  | 141    | Segregated Witness                   | Final  | Core     | Eric Lombrozo          | SegWit consensus layer             |
      | bip-340   | bitcoin  | bip  | 340    | Schnorr Signatures for secp256k1     | Final  | Core     | Pieter Wuille         | Schnorr signature scheme           |
      | bip-341   | bitcoin  | bip  | 341    | Taproot SegWit version 1             | Final  | Core     | Pieter Wuille         | Taproot spending rules             |
      | simd-0096 | solana   | simd | 96     | Reward full priority fee             | Final  | Core     | Tao Zhu               | Priority fee goes to validator     |

  Scenario: Search by exact proposal ID
    When I search for "eip-1559"
    Then the first result should be "eip-1559"
    And there should be 1 result

  Scenario: Search by keyword returns cross-chain results
    When I search for "fee"
    Then results should include "eip-1559"
    And results should include "simd-0096"

  Scenario: Search by concept finds related proposals
    When I search for "token standard"
    Then results should include "erc-20"

  Scenario: Search for taproot finds Bitcoin BIPs
    When I search for "taproot"
    Then results should include "bip-341"
    And results should be from chain "bitcoin"

  Scenario: Search returns empty for nonsense query
    When I search for "xyzzy123foobarbaz"
    Then there should be 0 results

  Scenario: Search handles special characters safely
    When I search for "fee* OR (market)"
    Then the search should not raise an error
