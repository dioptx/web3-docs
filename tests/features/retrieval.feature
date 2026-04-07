Feature: Proposal Retrieval
  As a web3 developer using an AI assistant
  I want to retrieve full or targeted sections of a protocol proposal
  So that I can understand specific aspects without reading the entire document

  Background:
    Given a database with a proposal "eip-1559"
      | field          | value                                              |
      | chain          | ethereum                                           |
      | type           | eip                                                |
      | number         | 1559                                               |
      | title          | Fee market change for ETH 1.0 chain                |
      | status         | Final                                              |
      | category       | Core                                               |
      | authors        | Vitalik Buterin                                    |
      | created        | 2019-04-13                                         |
      | requires       | 2718, 2930                                         |
      | discussions_to | https://ethereum-magicians.org/t/eip-1559           |
      | body           | ## Abstract\n\nA base fee mechanism.\n\n## Specification\n\nThe base fee is calculated as follows.\n\n## Security Considerations\n\nMiner extractable value concerns.\n\n## Rationale\n\nWhy we chose this design. |

  Scenario: Retrieve full proposal without query
    When I retrieve proposal "eip-1559" without a query
    Then the response should contain "Fee market change"
    And the response should contain "status: Final"
    And the response should contain "discussion: https://ethereum-magicians.org/t/eip-1559"
    And the response should contain "requires: 2718, 2930"
    And the response should contain "## Abstract"

  Scenario: Retrieve targeted sections with a query
    When I retrieve proposal "eip-1559" with query "security"
    Then the response should contain "Security Considerations"
    And the response should contain "Miner extractable value"

  Scenario: Retrieve returns abstract even with specific query
    When I retrieve proposal "eip-1559" with query "base fee calculation"
    Then the response should contain "Abstract"

  Scenario: Retrieve non-existent proposal
    When I retrieve proposal "eip-99999" without a query
    Then the response should contain "not found"

  Scenario: Enriched metadata appears in header
    When I retrieve proposal "eip-1559" without a query
    Then the response should contain "chain: ethereum"
    And the response should contain "type: eip"
    And the response should contain "authors: Vitalik Buterin"
    And the response should contain "created: 2019-04-13"
